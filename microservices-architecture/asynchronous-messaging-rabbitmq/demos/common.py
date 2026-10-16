import json
import os
import time
from typing import Any

import pika


RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "student")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "student")


def connection(max_attempts: int = 30, delay_seconds: float = 1.0) -> pika.BlockingConnection:
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
    parameters = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        port=RABBITMQ_PORT,
        credentials=credentials,
        heartbeat=30,
        blocked_connection_timeout=30,
    )

    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return pika.BlockingConnection(parameters)
        except pika.exceptions.AMQPConnectionError as exc:
            last_error = exc
            print(f"RabbitMQ not ready (attempt {attempt}/{max_attempts})")
            time.sleep(delay_seconds)

    raise RuntimeError("RabbitMQ did not become available") from last_error


def encode(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def decode(body: bytes) -> dict[str, Any]:
    return json.loads(body.decode("utf-8"))


def persistent_json_properties(**kwargs: Any) -> pika.BasicProperties:
    return pika.BasicProperties(
        content_type="application/json",
        delivery_mode=2,
        **kwargs,
    )
