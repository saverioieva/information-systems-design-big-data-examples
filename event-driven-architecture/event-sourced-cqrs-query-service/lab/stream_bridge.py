"""Reliable RabbitMQ integration-events -> Kafka bridge.

The Saga still uses RabbitMQ for commands/replies. Each microservice commits
its events and RabbitMQ outbox atomically. This bridge ACKs its durable Rabbit
queue only after Kafka confirms production. Kafka can receive duplicates on
crash/retry; the history projection handles those idempotently.
"""
from __future__ import annotations

import json
import logging
import os
import time

from confluent_kafka import Producer
import pika

from lab.messaging import EXCHANGE

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)
QUEUE = "es.saga.integration-to-kafka"


def publish_and_wait(producer: Producer, topic: str, envelope: dict) -> None:
    status = []

    def delivered(error, message):
        status.append(error)

    producer.produce(
        topic,
        key=envelope["order_id"].encode("utf-8"),
        value=json.dumps(envelope).encode("utf-8"),
        on_delivery=delivered,
    )
    remaining = producer.flush(12)
    if remaining or not status or status[0] is not None:
        raise RuntimeError(f"Kafka did not confirm integration event: {status}")


def main():
    rabbit_url = os.getenv("RABBITMQ_URL", "amqp://lab:lab@rabbit:5672/%2F")
    kafka_bootstrap = os.getenv("KAFKA_BOOTSTRAP", "kafka:19092")
    topic = os.getenv("KAFKA_TOPIC", "orders.integration")
    producer = Producer({
        "bootstrap.servers": kafka_bootstrap,
        "acks": "all",
        "enable.idempotence": True,
    })
    while True:
        connection = None
        try:
            connection = pika.BlockingConnection(pika.URLParameters(rabbit_url))
            channel = connection.channel()
            channel.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)
            channel.queue_declare(queue=QUEUE, durable=True)
            channel.queue_bind(exchange=EXCHANGE, queue=QUEUE, routing_key="integration.#")
            channel.basic_qos(prefetch_count=1)
            log.info("Bridge ready: RabbitMQ %s -> Kafka %s", QUEUE, topic)
            for method, _properties, body in channel.consume(QUEUE, inactivity_timeout=1):
                if method is None:
                    continue
                try:
                    envelope = json.loads(body)
                    if not envelope["type"].startswith("integration."):
                        raise ValueError("Only integration events belong on this bridge")
                    publish_and_wait(producer, topic, envelope)
                    channel.basic_ack(delivery_tag=method.delivery_tag)
                except Exception:
                    log.exception("Bridge did not confirm Kafka record: redelivering")
                    channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                    time.sleep(1)
        except Exception:
            log.exception("Bridge reconnecting")
            time.sleep(2)
        finally:
            if connection is not None and connection.is_open:
                connection.close()


if __name__ == "__main__":
    main()
