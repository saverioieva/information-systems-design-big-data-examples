"""Settings shared by the AMQP 1.0 Proton producer and consumer.

RabbitMQ address syntax (v2) is broker-specific, not part of AMQP 1.0.
"""

import os
from urllib.parse import quote


QUEUE_NAME = os.getenv("AMQP10_QUEUE", "orders.amqp10")
# RabbitMQ 4.0+ AMQP 1.0 v2 address (requires a pre-existing queue).
ADDRESS = f"/queues/{quote(QUEUE_NAME, safe='')}"
HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
USER = os.getenv("RABBITMQ_USER", "student")
PASSWORD = os.getenv("RABBITMQ_PASSWORD", "student")


def connect():
    """Connect using AMQP 1.0, not Pika/AMQP 0-9-1."""
    from proton.utils import BlockingConnection

    # This classroom lab uses plaintext only on the isolated Docker network.
    # For production, prefer TLS (amqps) and proper secret management.
    return BlockingConnection(
        f"amqp://{HOST}:{PORT}",
        user=USER,
        password=PASSWORD,
        allowed_mechs="PLAIN",
        allow_insecure_mechs=True,
        timeout=30,
    )
