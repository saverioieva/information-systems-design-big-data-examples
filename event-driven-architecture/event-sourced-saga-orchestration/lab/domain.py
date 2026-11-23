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


def _reply(kind: str, original: dict[str, Any], **data: Any) -> dict[str, Any]:
    return message(kind, original["order_id"], data, saga_id=original.get("saga_id", ""),
                   seed=original["message_id"])


def process(role: str, incoming: dict[str, Any], state: dict[str, Any]) -> Decision:
    """Validate a command/reply and *propose* events and outgoing messages.

    No mutation of the state and no database or RabbitMQ access occurs here.
    The event store commits events, inbox and outbox in one local transaction.
    """
    kind = incoming["type"]
    oid = incoming["order_id"]
    saga = incoming.get("saga_id", "")
    data = incoming.get("data", {})
    result = Decision()

    if role == "orchestrator":
        if kind == "order.created":
            if state["exists"]:
                return result
            result.events.append(("SagaOrchestratorCreated", {"order_id": oid}))
            command = message("command.account.authorize", oid,
                              {"amount": data["total"], "restaurant_id": data["restaurant_id"],
                               "reject": bool(data.get("reject", False))}, saga_id=f"saga:{oid}")
            result.events.append(("SagaCommandRequested", {"step": "AUTHORIZING", "command_type": command["type"],
                                                          "message_id": command["message_id"]}))
            result.messages.append(command)
            return result
        # A late or repeated reply must not move an already-advanced saga backward.
        transitions = {
            ("AUTHORIZING", "reply.account.authorized"):
                ("TICKETING", "command.kitchen.prepare", {"restaurant_id": data.get("restaurant_id", "demo-restaurant"),
                                                            "reject": data.get("reject", False)}),
            ("TICKETING", "reply.kitchen.accepted"):
                ("APPROVING", "command.order.approve", {}),
            ("TICKETING", "reply.kitchen.rejected"):
                ("VOIDING", "command.account.void", {}),
            ("VOIDING", "reply.account.voided"):
                ("CANCELLING", "command.order.cancel", {}),
        }
        # The original kitchen scenario must survive the Accounting round-trip.
        if kind == "reply.account.authorized" and state.get("step") == "AUTHORIZING":
            target_step, command_kind, _ = transitions[("AUTHORIZING", kind)]
            command_data = {"restaurant_id": data.get("restaurant_id", "demo-restaurant"),
                            "reject": bool(data.get("reject", False))}
        else:
            transition = transitions.get((state.get("step"), kind))
            if transition is None:
                if (state.get("step"), kind) == ("APPROVING", "reply.order.approved"):
                    result.events.extend([
                        ("SagaReplyReceived", {"reply_type": kind}),
                        ("SagaCompleted", {"order_id": oid}),
                    ])
                elif (state.get("step"), kind) == ("CANCELLING", "reply.order.cancelled"):
                    result.events.extend([
                        ("SagaReplyReceived", {"reply_type": kind}),
                        ("SagaCompensated", {"order_id": oid}),
                    ])
                return result
            target_step, command_kind, command_data = transition
        command = message(command_kind, oid, command_data, saga_id=f"saga:{oid}")
        result.events.extend([
            ("SagaReplyReceived", {"reply_type": kind}),
            ("SagaCommandRequested", {"step": target_step, "command_type": command_kind,
                                      "message_id": command["message_id"]}),
        ])
        result.messages.append(command)
        return result

    if role == "accounting":
        if kind == "command.account.authorize":
            if not state["exists"]:
                result.events.append(("AccountAuthorized", {"order_id": oid, "amount": data["amount"]}))
            elif state.get("status") != "AUTHORIZED":
                raise ValueError("Cannot authorize a voided account")
            reply = _reply("reply.account.authorized", incoming,
                           restaurant_id=data.get("restaurant_id", "demo-restaurant"),
                           reject=bool(data.get("reject", False)))
        elif kind == "command.account.void":
            if state.get("status") == "AUTHORIZED":
                result.events.append(("AuthorizationVoided", {"order_id": oid}))
            elif state.get("status") != "VOIDED":
                raise ValueError("Authorization to void was not found")
            reply = _reply("reply.account.voided", incoming)
        else:
            raise ValueError(f"Unknown accounting command: {kind}")
        # A pseudo-event records intent to reply even when no business change occurs.
        result.events.append(("SagaReplyRequested", {"reply_id": reply["message_id"],
                                                      "reply_type": reply["type"]}))
        result.messages.append(reply)
        return result

    if role == "kitchen":
        if kind != "command.kitchen.prepare":
            raise ValueError(f"Unknown kitchen command: {kind}")
        if not state["exists"]:
            rejected = bool(data.get("reject", False))
            result.events.append(("TicketRejected" if rejected else "TicketAccepted",
                                  {"order_id": oid, "restaurant_id": data.get("restaurant_id", "demo-restaurant")}))
        reply_type = "reply.kitchen.rejected" if (state.get("status") == "REJECTED" or
                                                   (not state["exists"] and data.get("reject", False))) else "reply.kitchen.accepted"
        reply = _reply(reply_type, incoming)
        result.events.append(("SagaReplyRequested", {"reply_id": reply["message_id"],
                                                      "reply_type": reply["type"]}))
        result.messages.append(reply)
        return result

    if role == "order":
        if kind == "command.order.approve":
            if state.get("status") == "PENDING":
                result.events.append(("OrderApproved", {"order_id": oid}))
            elif state.get("status") != "APPROVED":
                raise ValueError("Cannot approve a cancelled order")
            reply = _reply("reply.order.approved", incoming)
        elif kind == "command.order.cancel":
            if state.get("status") == "PENDING":
                result.events.append(("OrderCancelled", {"order_id": oid}))
            elif state.get("status") != "CANCELLED":
                raise ValueError("Cannot cancel an approved order")
            reply = _reply("reply.order.cancelled", incoming)
        else:
            raise ValueError(f"Unknown order command: {kind}")
        result.events.append(("SagaReplyRequested", {"reply_id": reply["message_id"],
                                                      "reply_type": reply["type"]}))
        result.messages.append(reply)
        return result

    raise ValueError(f"Unknown service role: {role}")


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
