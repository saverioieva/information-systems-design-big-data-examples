"""Persistence port for Audit Consumer's delivery/idempotency records."""
from typing import Protocol

class AuditRepository(Protocol):
    def record_received(self, event_id: str, order_id: str) -> None: ...
