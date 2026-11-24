"""Explicit event replay and pure decision logic for four separate aggregates.

This intentionally small implementation makes the process(command) / apply(event)
mechanics visible after the preceding lab's framework-backed example.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid5


NAMESPACE = UUID("0b504518-3e99-4717-a327-7bb655110099")


def stable_id(*parts: str) -> str:
    return str(uuid5(NAMESPACE, ":".join(parts)))


def message(kind: str, order_id: str, data: dict[str, Any], *, saga_id: str = "", seed: str = "") -> dict[str, Any]:
    return {
        "message_id": stable_id("message", order_id, kind, seed or saga_id),
        "type": kind,
        "order_id": order_id,
        "saga_id": saga_id,
        "data": data,
    }


@dataclass
class Decision:
    events: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    messages: list[dict[str, Any]] = field(default_factory=list)


def apply(role: str, state: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    """Apply a past event deterministically (no I/O, no business commands)."""
    state = dict(state)
    kind = record["type"]
    data = record["data"]
    state["exists"] = True
    state["version"] = int(record["version"])
    if role == "order":
        if kind == "OrderCreated":
            state.update(order_id=data["order_id"], consumer_id=data["consumer_id"],
                         restaurant_id=data["restaurant_id"], total=data["total"], status="PENDING")
        elif kind == "OrderApproved":
            state["status"] = "APPROVED"
        elif kind == "OrderCancelled":
            state["status"] = "CANCELLED"
    elif role == "accounting":
        if kind == "AccountAuthorized":
            state.update(order_id=data["order_id"], authorized_amount=data["amount"], status="AUTHORIZED")
        elif kind == "AuthorizationVoided":
            state["status"] = "VOIDED"
    elif role == "kitchen":
        if kind in ("TicketAccepted", "TicketRejected"):
            state.update(order_id=data["order_id"], restaurant_id=data["restaurant_id"],
                         status="ACCEPTED" if kind == "TicketAccepted" else "REJECTED")
    elif role == "orchestrator":
        if kind == "SagaOrchestratorCreated":
            state.update(order_id=data["order_id"], status="RUNNING", step="CREATED")
        elif kind == "SagaCommandRequested":
            state["step"] = data["step"]
        elif kind == "SagaReplyReceived":
            state["last_reply"] = data["reply_type"]
        elif kind == "SagaCompleted":
            state.update(status="COMPLETED", step="DONE")
        elif kind == "SagaCompensated":
            state.update(status="COMPENSATED", step="DONE")
    return state


def evolve(role: str, history: list[dict[str, Any]]) -> dict[str, Any]:
    """Replay one Aggregate stream with the same apply() used for new events."""
    state: dict[str, Any] = {"exists": False, "version": 0}
    for record in history:
        state = apply(role, state, record)
    return state


# These are local domain commands, NOT RabbitMQ message envelopes.
# A participant's Saga adapter chooses which command to invoke.
@dataclass(frozen=True)
class CreateOrder:
    order_id: str
    consumer_id: str
    restaurant_id: str
    items: list[dict[str, Any]]
    total: float
    reject: bool = False


@dataclass(frozen=True)
class AuthorizeAccount:
    order_id: str
    amount: float


@dataclass(frozen=True)
class VoidAuthorization:
    order_id: str


@dataclass(frozen=True)
class PrepareTicket:
    order_id: str
    restaurant_id: str
    reject: bool = False


@dataclass(frozen=True)
class ApproveOrder:
    order_id: str


@dataclass(frozen=True)
class CancelOrder:
    order_id: str


DomainCommand = (CreateOrder | AuthorizeAccount | VoidAuthorization |
                 PrepareTicket | ApproveOrder | CancelOrder)


def process(command: DomainCommand, state: dict[str, Any]) -> Decision:
    """Aggregate command decision: validate invariants and propose domain events.

    No transport message, reply, Event Store, or I/O is involved. This is the
    explicit process(command) step shown in the lecture slides. apply(event)
    reconstructs state from the persisted events independently of the command.
    """
    result = Decision()
    oid = command.order_id
    if isinstance(command, CreateOrder):
        if state["exists"]:
            raise ValueError("Order already exists")
        if not command.items or any(int(i["quantity"]) <= 0 or float(i["price"]) <= 0
                                    for i in command.items):
            raise ValueError("The order needs positive-quantity, positive-price items")
        result.events.append(("OrderCreated", {
            "order_id": oid, "consumer_id": command.consumer_id,
            "restaurant_id": command.restaurant_id, "items": command.items,
            "total": command.total, "reject": command.reject,
        }))
    elif isinstance(command, AuthorizeAccount):
        if command.amount <= 0:
            raise ValueError("Authorization amount must be positive")
        if not state["exists"]:
            result.events.append(("AccountAuthorized", {"order_id": oid, "amount": command.amount}))
        elif state.get("status") != "AUTHORIZED":
            raise ValueError("Cannot authorize a voided account")
    elif isinstance(command, VoidAuthorization):
        if state.get("status") == "AUTHORIZED":
            result.events.append(("AuthorizationVoided", {"order_id": oid}))
        elif state.get("status") != "VOIDED":
            raise ValueError("Authorization to void was not found")
    elif isinstance(command, PrepareTicket):
        if not state["exists"]:
            result.events.append(("TicketRejected" if command.reject else "TicketAccepted", {
                "order_id": oid, "restaurant_id": command.restaurant_id,
            }))
    elif isinstance(command, ApproveOrder):
        if state.get("status") == "PENDING":
            result.events.append(("OrderApproved", {"order_id": oid}))
        elif state.get("status") != "APPROVED":
            raise ValueError("Cannot approve a cancelled order")
    elif isinstance(command, CancelOrder):
        if state.get("status") == "PENDING":
            result.events.append(("OrderCancelled", {"order_id": oid}))
        elif state.get("status") != "CANCELLED":
            raise ValueError("Cannot cancel an approved order")
    else:
        raise TypeError(f"Unknown aggregate command: {type(command).__name__}")
    return result


INTEGRATION_EVENTS = {
    "OrderCreated": "integration.order.created",
    "OrderApproved": "integration.order.approved",
    "OrderCancelled": "integration.order.cancelled",
    "AccountAuthorized": "integration.accounting.authorized",
    "AuthorizationVoided": "integration.accounting.voided",
    "TicketAccepted": "integration.kitchen.accepted",
    "TicketRejected": "integration.kitchen.rejected",
}


def integration_message(role: str, event_type: str, order_id: str, version: int,
                        event_id: str, event_data: dict[str, Any]) -> dict[str, Any] | None:
    route = INTEGRATION_EVENTS.get(event_type)
    if route is None:
        return None
    return {"message_id": event_id, "type": route, "order_id": order_id,
            "source": role, "version": version, "data": event_data}
