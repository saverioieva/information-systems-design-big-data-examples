"""Forward to RabbitMQ first; the caller commits Kafka offsets afterwards."""
from bridge.domain.routing import translate


def forward(message: bytes, publisher):
    record = translate(message)
    publisher.publish(record)  # must wait for RabbitMQ publisher confirmation
    return record
