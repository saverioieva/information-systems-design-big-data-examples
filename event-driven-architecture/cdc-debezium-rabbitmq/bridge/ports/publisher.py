"""Outgoing bridge port; no broker-specific import in the application."""
from typing import Protocol
from bridge.domain.routing import RoutedEvent


class Publisher(Protocol):
    def publish(self, record: RoutedEvent) -> None: ...
