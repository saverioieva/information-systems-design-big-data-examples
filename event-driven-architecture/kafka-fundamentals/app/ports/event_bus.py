"""Outbound messaging port used by the application layer."""
from typing import Protocol


class EventProducer(Protocol):
    def send(self, *, key: str, value: bytes) -> None: ...
    def flush(self) -> None: ...
