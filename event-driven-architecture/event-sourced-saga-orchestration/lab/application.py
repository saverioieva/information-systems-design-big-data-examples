"""Application layer: transactional Event Store + Aggregate decisions + Saga reply intent.

This coordinates the domain's process(command) with reliable Inbox/Outbox storage.
Neither the domain nor the Aggregate knows RabbitMQ routing keys or reply messages.
"""
from __future__ import annotations

from typing import Any, Callable

from lab.domain import Decision, DomainCommand, process
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lab.storage import EventStore


class AggregateApplicationService:
    def __init__(self, store: EventStore, role: str, aggregate_type: str):
        self.store = store
        self.role = role
        self.aggregate_type = aggregate_type

    def execute(self, command: DomainCommand, *, message_id: str | None,
                reply_for: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
                messages_for: Callable[[Decision], list[dict[str, Any]]] | None = None):
        def decide(state: dict[str, Any]) -> Decision:
            decision = process(command, state)
            if reply_for is not None:
                reply = reply_for(state)
                # SagaReplyRequested is a technical pseudo-event; NOT an aggregate
                # business decision. A valid already-satisfied command still replies.
                decision.events.append(("SagaReplyRequested", {
                    "reply_id": reply["message_id"], "reply_type": reply["type"],
                }))
                decision.messages.append(reply)
            if messages_for is not None:
                decision.messages.extend(messages_for(decision))
            return decision

        return self.store.execute(
            role=self.role, aggregate_type=self.aggregate_type,
            aggregate_id=command.order_id, message_id=message_id, decide=decide,
        )
