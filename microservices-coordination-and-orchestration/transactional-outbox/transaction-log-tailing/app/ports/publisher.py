"""Outgoing port: the application layer does not depend on RabbitMQ."""
from typing import Protocol, Mapping, Any

class EventPublisher(Protocol):
    def publish(self, event: Mapping[str, Any]) -> None: ...
