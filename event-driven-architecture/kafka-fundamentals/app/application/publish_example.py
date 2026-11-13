"""The application knows the event key, not Kafka configuration details."""
from app.domain.messages import example_message, serialize_event


def produce_examples(producer, *, count: int, prefix: str = "DEMO") -> list[str]:
    ids = []
    for i in range(count):
        event = example_message(i, prefix=prefix)
        producer.send(key=event.orderId, value=serialize_event(event))
        ids.append(event.eventId)
    producer.flush()
    return ids
