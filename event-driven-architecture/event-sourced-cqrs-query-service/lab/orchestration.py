"""Event-sourced Saga Orchestrator decisions (separate from participant aggregates)."""
from __future__ import annotations

from typing import Any
from lab.domain import Decision, message


def advance_saga(incoming: dict[str, Any], state: dict[str, Any]) -> Decision:
    """Process an OrderCreated notification or participant reply into Saga events/commands.

    The Orchestrator controls the workflow, but never writes a participant's
    domain events; each participant processes its own local domain command.
    """
    kind = incoming["type"]
    oid = incoming["order_id"]
    data = incoming.get("data", {})
    result = Decision()
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
