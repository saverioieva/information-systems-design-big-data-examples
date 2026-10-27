"""Outbound messaging port, independent of Pika."""
from typing import Protocol

class ValidationPublisher(Protocol):
    def publish_requests(self, order_id: str, consumer_id: str, item: str) -> None: ...
