"""Dedicated Saga participant adapters: wire command -> local Aggregate command.

Each service owns an inbound Saga handler; RabbitMQ commands are NOT applied as
Aggregate events. They are translated into domain commands and validated by
process(command), then the application layer registers the reply atomically.
"""
from __future__ import annotations

from typing import Any

from lab.application import AggregateApplicationService
from lab.domain import (AuthorizeAccount, VoidAuthorization, PrepareTicket,
                        ApproveOrder, CancelOrder, message)
from lab.orchestration import advance_saga
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lab.storage import EventStore


def _reply(kind: str, original: dict[str, Any], **data: Any) -> dict[str, Any]:
    return message(kind, original["order_id"], data, saga_id=original.get("saga_id", ""),
                   seed=original["message_id"])


class AccountingSagaHandler:
    def handle(self, store: EventStore, incoming: dict[str, Any]) -> bool:
        oid = incoming["order_id"]
        data = incoming.get("data", {})
        kind = incoming["type"]
        if kind == "command.account.authorize":
            command = AuthorizeAccount(oid, float(data["amount"]))
            reply = _reply("reply.account.authorized", incoming,
                           restaurant_id=data.get("restaurant_id", "demo-restaurant"),
                           reject=bool(data.get("reject", False)))
        elif kind == "command.account.void":
            command = VoidAuthorization(oid)
            reply = _reply("reply.account.voided", incoming)
        else:
            raise ValueError(f"Unknown Accounting Saga command: {kind}")
        _, fresh = AggregateApplicationService(store, "accounting", "AccountAuthorization").execute(
            command, message_id=incoming["message_id"], reply_for=lambda _state: reply,
        )
        return fresh


class KitchenSagaHandler:
    def handle(self, store: EventStore, incoming: dict[str, Any]) -> bool:
        if incoming["type"] != "command.kitchen.prepare":
            raise ValueError(f"Unknown Kitchen Saga command: {incoming['type']}")
        data = incoming.get("data", {})
        command = PrepareTicket(incoming["order_id"], data.get("restaurant_id", "demo-restaurant"),
                                bool(data.get("reject", False)))

        def choose_reply(state):
            # A previously decided ticket status wins over repeated commands.
            rejected = (state.get("status") == "REJECTED" or
                        (not state["exists"] and command.reject))
            return _reply("reply.kitchen.rejected" if rejected else "reply.kitchen.accepted", incoming)

        _, fresh = AggregateApplicationService(store, "kitchen", "KitchenTicket").execute(
            command, message_id=incoming["message_id"], reply_for=choose_reply,
        )
        return fresh


class OrderSagaHandler:
    def handle(self, store: EventStore, incoming: dict[str, Any]) -> bool:
        kind = incoming["type"]
        oid = incoming["order_id"]
        if kind == "command.order.approve":
            command, reply_kind = ApproveOrder(oid), "reply.order.approved"
        elif kind == "command.order.cancel":
            command, reply_kind = CancelOrder(oid), "reply.order.cancelled"
        else:
            raise ValueError(f"Unknown Order Saga command: {kind}")
        reply = _reply(reply_kind, incoming)
        _, fresh = AggregateApplicationService(store, "order", "Order").execute(
            command, message_id=incoming["message_id"], reply_for=lambda _state: reply,
        )
        return fresh


class SagaOrchestratorHandler:
    def handle(self, store: EventStore, incoming: dict[str, Any]) -> bool:
        # The Orchestrator consumes a business notification and Saga replies,
        # while participants consume COMMANDS and decide their own domain events.
        kind = incoming["type"]
        if kind != "order.created" and not kind.startswith("reply."):
            raise ValueError(f"Unknown Saga Orchestrator message: {kind}")
        oid = incoming["order_id"]
        _, fresh = store.execute(
            role="orchestrator", aggregate_type="SagaOrchestrator",
            aggregate_id=f"saga:{oid}", message_id=incoming["message_id"],
            decide=lambda state: advance_saga(incoming, state),
        )
        return fresh


HANDLERS = {
    "order": OrderSagaHandler(),
    "accounting": AccountingSagaHandler(),
    "kitchen": KitchenSagaHandler(),
    "orchestrator": SagaOrchestratorHandler(),
}
