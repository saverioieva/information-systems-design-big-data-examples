"""Outbound persistence port owned by the Audit Consumer."""
from typing import Protocol


class AuditRepository(Protocol):
    def record_delivery(self, event_id: str, order_id: str) -> None: ...
