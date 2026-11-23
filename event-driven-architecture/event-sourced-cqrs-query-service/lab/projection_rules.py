"""Pure mapping from immutable integration events to query-optimized columns."""
from __future__ import annotations

from typing import Any


def changes_for(kind: str, data: dict[str, Any]) -> dict[str, Any]:
    if kind == "integration.order.created":
        return {"consumer_id": data["consumer_id"], "restaurant_id": data["restaurant_id"],
                "total": data["total"], "order_status": "PENDING"}
    if kind == "integration.order.approved":
        return {"order_status": "APPROVED"}
    if kind == "integration.order.cancelled":
        return {"order_status": "CANCELLED"}
    if kind == "integration.accounting.authorized":
        return {"payment_status": "AUTHORIZED"}
    if kind == "integration.accounting.voided":
        return {"payment_status": "VOIDED"}
    if kind == "integration.kitchen.accepted":
        return {"kitchen_status": "ACCEPTED"}
    if kind == "integration.kitchen.rejected":
        return {"kitchen_status": "REJECTED"}
    raise ValueError(f"Unsupported integration event: {kind}")
