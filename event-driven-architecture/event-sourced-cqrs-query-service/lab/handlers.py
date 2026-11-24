"""Inbound HTTP and broker use cases; individual Saga adapters own message mapping."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from lab.application import AggregateApplicationService
from lab.domain import CreateOrder, message
from lab.saga_handlers import HANDLERS
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lab.storage import EventStore


def create_order(store: EventStore, payload: dict[str, Any]) -> dict[str, Any]:
    oid = str(uuid4())
    items = payload["items"]
    if not items or any(x["quantity"] <= 0 or x["price"] <= 0 for x in items):
        raise ValueError("The order needs positive-quantity, positive-price items")
    total = round(sum(float(x["price"]) * int(x["quantity"]) for x in items), 2)
    command = CreateOrder(oid, payload["consumer_id"], payload["restaurant_id"],
                          items, total, bool(payload.get("reject_kitchen", False)))

    def start_saga(decision):
        # Forward OrderCreated (business notification), not a foreign domain event.
        return [message("order.created", oid, decision.events[0][1])]

    state, _ = AggregateApplicationService(store, "order", "Order").execute(
        command, message_id=None, messages_for=start_saga,
    )
    return state


def handle_delivery(store: EventStore, role: str, msg: dict[str, Any]) -> bool:
    if not all(field in msg for field in ("message_id", "order_id", "type")):
        raise ValueError("Invalid Saga message envelope")
    try:
        handler = HANDLERS[role]
    except KeyError as exc:
        raise ValueError(f"Unknown service role: {role}") from exc
    return handler.handle(store, msg)
