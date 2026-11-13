"""Small immutable integration-event DTO. No dependency on Kafka or RabbitMQ."""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from uuid import uuid4


@dataclass(frozen=True)
class IntegrationEvent:
    eventId: str
    type: str
    orderId: str
    amount: float
    status: str
    occurredAt: str

    def as_dict(self):
        return asdict(self)


def new_event(kind: str, order_id: str, amount: float, status: str) -> IntegrationEvent:
    if kind not in {"OrderCreated", "OrderApproved"}:
        raise ValueError("Unsupported integration event type")
    return IntegrationEvent(
        eventId=str(uuid4()), type=kind, orderId=order_id,
        amount=float(amount), status=status,
        occurredAt=datetime.now(timezone.utc).isoformat(),
    )
