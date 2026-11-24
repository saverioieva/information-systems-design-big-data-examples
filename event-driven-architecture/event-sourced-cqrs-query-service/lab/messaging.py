"""Durable RabbitMQ topic exchange and at-least-once Outbox relay."""
from __future__ import annotations

import json
import logging
import os
import threading
import time

import pika

from lab.handlers import handle_delivery
from lab.storage import EventStore

log = logging.getLogger(__name__)
EXCHANGE = "es.saga.bus"
BINDINGS = {
    "order": ["command.order.*"],
    "accounting": ["command.account.*"],
    "kitchen": ["command.kitchen.*"],
    "orchestrator": ["order.created", "reply.#"],
}


class MessageWorker:
    def __init__(self, role: str, store: EventStore):
        self.role = role
        self.store = store
        self.url = os.getenv("RABBITMQ_URL", "amqp://lab:lab@rabbit:5672/%2F")
        self.stop_event = threading.Event()
        self.threads: list[threading.Thread] = []

    def _channel(self):
        connection = pika.BlockingConnection(pika.URLParameters(self.url))
        channel = connection.channel()
        channel.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)
        return connection, channel

    def start(self):
        # Declare durable Saga command/reply queues before HTTP readiness.
        for attempt in range(30):
            connection = None
            try:
                connection, channel = self._channel()
                queue_name = f"es.saga.{self.role}"
                channel.queue_declare(queue=queue_name, durable=True)
                for binding in BINDINGS[self.role]:
                    channel.queue_bind(exchange=EXCHANGE, queue=queue_name, routing_key=binding)
                break
            except Exception:
                if attempt == 29:
                    raise
                time.sleep(1)
            finally:
                if connection and connection.is_open:
                    connection.close()
        self.threads.append(threading.Thread(target=self._consumer_loop, daemon=True, name=f"{self.role}-inbox"))
        self.threads.append(threading.Thread(target=self._publisher_loop, daemon=True,
                                             name=f"{self.role}-outbox"))
        for thread in self.threads:
            thread.start()

    def stop(self):
        self.stop_event.set()
        for thread in self.threads:
            thread.join(timeout=2)

    def _consumer_loop(self):
        while not self.stop_event.is_set():
            connection = None
            try:
                connection, channel = self._channel()
                queue_name = f"es.saga.{self.role}"
                channel.queue_declare(queue=queue_name, durable=True)
                for binding in BINDINGS[self.role]:
                    channel.queue_bind(exchange=EXCHANGE, queue=queue_name, routing_key=binding)
                channel.basic_qos(prefetch_count=1)
                for method, _properties, body in channel.consume(queue_name, inactivity_timeout=1):
                    if self.stop_event.is_set():
                        break
                    if method is None:
                        continue
                    try:
                        envelope = json.loads(body)
                        handle_delivery(self.store, self.role, envelope)
                        channel.basic_ack(delivery_tag=method.delivery_tag)
                    except Exception:
                        log.exception("Could not process %s message; will retry", self.role)
                        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                        time.sleep(1)
            except Exception:
                if not self.stop_event.is_set():
                    log.exception("RabbitMQ consumer reconnecting (%s)", self.role)
                    self.stop_event.wait(2)
            finally:
                if connection and connection.is_open:
                    connection.close()

    def _publisher_loop(self):
        assert self.store is not None
        while not self.stop_event.is_set():
            connection = None
            try:
                connection, channel = self._channel()
                channel.confirm_delivery()

                def publish(routing_key, envelope):
                    # 'mandatory' also protects integration events until the
                    # durable Kafka bridge queue has been declared/bound.
                    channel.basic_publish(
                        exchange=EXCHANGE, routing_key=routing_key,
                        body=json.dumps(envelope).encode("utf-8"),
                        properties=pika.BasicProperties(delivery_mode=2,
                                                        content_type="application/json",
                                                        message_id=envelope["message_id"]),
                        mandatory=True,
                    )

                while not self.stop_event.is_set():
                    sent = self.store.send_pending(publish)
                    if sent == 0:
                        self.stop_event.wait(0.25)
            except Exception:
                if not self.stop_event.is_set():
                    log.exception("Outbox relay reconnecting (%s)", self.role)
                    self.stop_event.wait(2)
            finally:
                if connection and connection.is_open:
                    connection.close()
