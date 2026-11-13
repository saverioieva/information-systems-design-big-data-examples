"""Minimal event contract used for teaching Kafka topics and ordering."""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from uuid import uuid4
import json


@dataclass(frozen=True)
class OrderStatusChanged:
    eventId: str
    type: str
    orderId: str
    sequence: int
    status: str
    occurredAt: str


def example_message(index: int, prefix: str = "DEMO", number_of_orders: int = 4) -> OrderStatusChanged:
    if index < 0 or number_of_orders < 1:
        raise ValueError("Invalid example index or number of orders")
    return OrderStatusChanged(
        eventId=str(uuid4()),
        type="OrderStatusChanged",
        orderId=f"{prefix}-{index % number_of_orders:02d}",
        sequence=index,
        status=("CREATED", "APPROVAL_PENDING", "APPROVED")[index % 3],
        occurredAt=datetime.now(timezone.utc).isoformat(),
    )


def serialize_event(event: OrderStatusChanged) -> bytes:
    return json.dumps(asdict(event), separators=(",", ":")).encode("utf-8")


def parse_event(value: bytes) -> dict:
    obj = json.loads(value)
    if not isinstance(obj, dict) or not obj.get("orderId") or not obj.get("eventId"):
        raise ValueError("Invalid event envelope")
    return obj
