"""RabbitMQ AMQP 0-9-1 helpers shared by the four demo processes."""
from __future__ import annotations

import json
import logging
import os
import time
import uuid

import pika

LOG = logging.getLogger(__name__)
CONSUMER_QUEUE = "validation.consumer"
RESTAURANT_QUEUE = "validation.restaurant"
RESULTS_QUEUE = "validation.results"
ALL_QUEUES = (CONSUMER_QUEUE, RESTAURANT_QUEUE, RESULTS_QUEUE)


def connect_with_retry(attempts: int = 40, pause: float = 2.0) -> pika.BlockingConnection:
    url = os.getenv("RABBITMQ_URL", "amqp://student:student@rabbitmq:5672/%2F")
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            return pika.BlockingConnection(pika.URLParameters(url))
        except pika.exceptions.AMQPConnectionError as exc:
            last_error = exc
            LOG.warning("RabbitMQ unavailable (%d/%d); retrying", attempt, attempts)
            time.sleep(pause)
    raise RuntimeError("Cannot connect to RabbitMQ") from last_error


def configure_channel(connection: pika.BlockingConnection):
    channel = connection.channel()
    for name in ALL_QUEUES:
        channel.queue_declare(queue=name, durable=True)
    channel.confirm_delivery()  # acknowledgments from the broker to the publisher
    return channel


def publish_json(channel, queue: str, message: dict) -> None:
    payload = json.dumps(message, separators=(",", ":"), sort_keys=True).encode("utf-8")
    channel.basic_publish(
        exchange="", routing_key=queue, body=payload, mandatory=True,
        properties=pika.BasicProperties(
            content_type="application/json",
            delivery_mode=2,
            message_id=str(uuid.uuid4()),
            correlation_id=message.get("order_id"),
        ),
    )


class RabbitMQValidationPublisher:
    """AMQP adapter: one message per validation service."""
    def publish_requests(self, order_id: str, consumer_id: str, item: str) -> None:
        common = {"order_id": order_id, "consumer_id": consumer_id, "item": item}
        conn = connect_with_retry(attempts=2, pause=0.5)
        try:
            channel = configure_channel(conn)
            publish_json(channel, CONSUMER_QUEUE, {"type": "ValidateConsumer", **common})
            publish_json(channel, RESTAURANT_QUEUE, {"type": "ValidateOrderDetails", **common})
        finally:
            if conn.is_open:
                conn.close()
