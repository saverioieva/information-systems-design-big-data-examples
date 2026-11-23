"""Inbound message use cases. No other service's database is ever accessed."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from lab.domain import Decision, evolve, message, process
from lab.storage import EventStore


def create_order(store: EventStore, payload: dict[str, Any]) -> dict[str, Any]:
    oid = str(uuid4())
    items = payload["items"]
    if not items or any(x["quantity"] <= 0 or x["price"] <= 0 for x in items):
        raise ValueError("The order needs positive-quantity, positive-price items")
    total = round(sum(float(x["price"]) * int(x["quantity"]) for x in items), 2)
    event_data = {
        "order_id": oid,
        "consumer_id": payload["consumer_id"],
        "restaurant_id": payload["restaurant_id"],
        "items": items,
        "total": total,
        "reject": bool(payload.get("reject_kitchen", False)),
    }
    # OrderCreated is appended in the same transaction as the Saga start request.
    decision = Decision(
        events=[("OrderCreated", event_data)],
        messages=[message("order.created", oid, event_data)],
    )
    state, _ = store.execute(role="order", aggregate_type="Order", aggregate_id=oid,
                             message_id=None, decide=lambda _: decision)
    return state


def handle_delivery(store: EventStore, role: str, msg: dict[str, Any]) -> bool:
    if "message_id" not in msg or "order_id" not in msg or "type" not in msg:
        raise ValueError("Invalid integration/command message envelope")
    oid = msg["order_id"]
    if role == "orchestrator":
        stream = f"saga:{oid}"
        aggregate_type = "SagaOrchestrator"
    else:
        stream = oid
        aggregate_type = {"order": "Order", "accounting": "AccountAuthorization", "kitchen": "KitchenTicket"}[role]
    _, fresh = store.execute(role=role, aggregate_type=aggregate_type, aggregate_id=stream,
                             message_id=msg["message_id"], decide=lambda state: process(role, msg, state))
    return fresh
