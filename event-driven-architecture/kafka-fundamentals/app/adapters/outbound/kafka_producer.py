"""Confluent Kafka producer adapter. Keyed events share a partition."""
import os
from confluent_kafka import Producer


class KafkaEventProducer:
    def __init__(self, topic: str | None = None):
        self.topic = topic or os.getenv("KAFKA_TOPIC", "orders.events")
        self.producer = Producer({
            "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP", "kafka:19092"),
            "acks": "all",
            "enable.idempotence": True,
        })
        self.errors = []

    def send(self, *, key: str, value: bytes) -> None:
        def on_delivery(err, msg):
            if err:
                self.errors.append(str(err))
            else:
                print(f"[producer] key={key} topic={msg.topic()} partition={msg.partition()} offset={msg.offset()}", flush=True)

        self.producer.produce(self.topic, key=key.encode(), value=value, on_delivery=on_delivery)
        self.producer.poll(0)

    def flush(self) -> None:
        remaining = self.producer.flush(timeout=30)
        if remaining or self.errors:
            raise RuntimeError(f"Kafka publish failed: remaining={remaining}, errors={self.errors}")
