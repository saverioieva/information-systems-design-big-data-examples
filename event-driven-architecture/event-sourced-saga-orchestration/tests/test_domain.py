"""The same tests run for both the Saga and CQRS applications."""
from dataclasses import dataclass, field

import pytest

from lab.domain import (ApproveOrder, AuthorizeAccount, CancelOrder, CreateOrder,
                        Decision, PrepareTicket, VoidAuthorization,
                        evolve, integration_message, message, process)
from lab.handlers import create_order, handle_delivery
from lab.orchestration import advance_saga
from lab.saga_handlers import (AccountingSagaHandler, KitchenSagaHandler, OrderSagaHandler,
                               SagaOrchestratorHandler)


def recorded(types):
    return [{"type": kind, "data": data, "version": index + 1}
            for index, (kind, data) in enumerate(types)]


@dataclass
class FakeEventStore:
    histories: dict[str, list[dict]] = field(default_factory=dict)
    seen: set[str] = field(default_factory=set)
    outbox: list[dict] = field(default_factory=list)
    calls: list[tuple] = field(default_factory=list)

    def execute(self, *, role, aggregate_type, aggregate_id, message_id, decide):
        self.calls.append((role, aggregate_type, aggregate_id, message_id))
        history = self.histories.setdefault(aggregate_id, [])
        state = evolve(role, history)
        if message_id in self.seen:
            return state, False
        decision = decide(state)
        for kind, payload in decision.events:
            history.append({"type": kind, "data": payload, "version": len(history) + 1})
        self.outbox.extend(decision.messages)
        if message_id is not None:
            self.seen.add(message_id)
        return evolve(role, history), True


def test_saga_happy_event_sourced_transitions():
    oid = "order-1"
    state = evolve("orchestrator", [])
    start = message("order.created", oid, {"total": 20, "restaurant_id": "r", "reject": False})
    decision = advance_saga(start, state)
    assert [x[0] for x in decision.events] == ["SagaOrchestratorCreated", "SagaCommandRequested"]
    state = evolve("orchestrator", recorded(decision.events))
    assert state["step"] == "AUTHORIZING"
    authorized = message("reply.account.authorized", oid, {"restaurant_id": "r", "reject": False})
    decision2 = advance_saga(authorized, state)
    assert decision2.messages[0]["type"] == "command.kitchen.prepare"
    state = evolve("orchestrator", recorded(decision.events + decision2.events))
    accepted = message("reply.kitchen.accepted", oid, {})
    decision3 = advance_saga(accepted, state)
    assert decision3.messages[0]["type"] == "command.order.approve"
    state = evolve("orchestrator", recorded(decision.events + decision2.events + decision3.events))
    finish = advance_saga(message("reply.order.approved", oid, {}), state)
    state = evolve("orchestrator", recorded(decision.events + decision2.events + decision3.events + finish.events))
    assert state["status"] == "COMPLETED"
    assert advance_saga(accepted, state).events == []


def test_saga_kitchen_rejection_triggers_void_before_cancel():
    oid = "order-2"
    events = advance_saga(message("order.created", oid,
                  {"total": 20, "restaurant_id": "r", "reject": True}), evolve("orchestrator", [])).events
    state = evolve("orchestrator", recorded(events))
    d = advance_saga(message("reply.account.authorized", oid, {"reject": True, "restaurant_id": "r"}), state)
    assert d.messages[0]["data"]["reject"] is True
    events += d.events
    state = evolve("orchestrator", recorded(events))
    d = advance_saga(message("reply.kitchen.rejected", oid, {}), state)
    assert d.messages[0]["type"] == "command.account.void"
    events += d.events
    state = evolve("orchestrator", recorded(events))
    d = advance_saga(message("reply.account.voided", oid, {}), state)
    assert d.messages[0]["type"] == "command.order.cancel"
    events += d.events
    state = evolve("orchestrator", recorded(events))
    d = advance_saga(message("reply.order.cancelled", oid, {}), state)
    assert evolve("orchestrator", recorded(events + d.events))["status"] == "COMPENSATED"


def test_aggregate_process_does_not_generate_transport_messages():
    authorize = process(AuthorizeAccount("o1", 10), evolve("accounting", []))
    assert authorize.events == [("AccountAuthorized", {"order_id": "o1", "amount": 10})]
    assert authorize.messages == []
    assert process(AuthorizeAccount("o1", 10), evolve("accounting", recorded(authorize.events))).events == []
    assert process(PrepareTicket("o1", "r", True), evolve("kitchen", [])).events[0][0] == "TicketRejected"


def test_accounting_handler_translates_saga_message_and_creates_reply_pseudo_event():
    store = FakeEventStore()
    cmd = message("command.account.authorize", "o1", {"amount": 20, "reject": False})
    assert handle_delivery(store, "accounting", cmd)
    assert store.calls[0][:3] == ("accounting", "AccountAuthorization", "o1")
    assert [x["type"] for x in store.histories["o1"]] == ["AccountAuthorized", "SagaReplyRequested"]
    assert store.outbox[-1]["type"] == "reply.account.authorized"
    assert handle_delivery(store, "accounting", cmd) is False
    assert len(store.histories["o1"]) == 2
    # Another, distinct command delivery can trigger a reply with no state change.
    cmd2 = message("command.account.authorize", "o1", {"amount": 20}, seed="new")
    assert handle_delivery(store, "accounting", cmd2)
    assert [x["type"] for x in store.histories["o1"]] == [
        "AccountAuthorized", "SagaReplyRequested", "SagaReplyRequested",
    ]


def test_kitchen_handler_reply_uses_existing_ticket_decision():
    store = FakeEventStore()
    initial = message("command.kitchen.prepare", "o1", {"reject": True, "restaurant_id": "r"})
    handle_delivery(store, "kitchen", initial)
    assert store.histories["o1"][0]["type"] == "TicketRejected"
    assert store.outbox[-1]["type"] == "reply.kitchen.rejected"
    repeated = message("command.kitchen.prepare", "o1", {"reject": False}, seed="new")
    handle_delivery(store, "kitchen", repeated)
    assert store.outbox[-1]["type"] == "reply.kitchen.rejected"
    assert len(store.histories["o1"]) == 3


def test_order_handler_cannot_bypass_aggregate_invariants():
    store = FakeEventStore()
    create_order(store, {"consumer_id": "c", "restaurant_id": "r",
                         "items": [{"price": 7, "quantity": 2}], "reject_kitchen": False})
    oid = next(iter(store.histories))
    handle_delivery(store, "order", message("command.order.approve", oid, {}))
    assert store.histories[oid][1]["type"] == "OrderApproved"
    with pytest.raises(ValueError, match="Cannot cancel"):
        handle_delivery(store, "order", message("command.order.cancel", oid, {}))


def test_orchestrator_handler_owns_saga_stream_not_participant_aggregate():
    store = FakeEventStore()
    start = message("order.created", "o1", {"total": 10, "restaurant_id": "r"})
    handle_delivery(store, "orchestrator", start)
    assert store.calls[-1][:3] == ("orchestrator", "SagaOrchestrator", "saga:o1")
    assert store.outbox[-1]["type"] == "command.account.authorize"
    assert handle_delivery(store, "orchestrator", start) is False
    assert len(store.histories["saga:o1"]) == 2


def test_all_services_have_distinct_saga_handlers():
    assert len({AccountingSagaHandler, KitchenSagaHandler, OrderSagaHandler, SagaOrchestratorHandler}) == 4


def test_integration_messages_include_aggregate_version():
    out = integration_message("order", "OrderApproved", "o1", 3, "e1", {"order_id": "o1"})
    assert out["type"] == "integration.order.approved"
    assert out["version"] == 3
    assert integration_message("orchestrator", "SagaCommandRequested", "o1", 5, "e2", {}) is None


def test_order_replay_is_independent_of_read_database():
    state = evolve("order", recorded([
        ("OrderCreated", {"order_id": "o1", "consumer_id": "c", "restaurant_id": "r", "total": 12}),
        ("OrderApproved", {"order_id": "o1"}),
        ("SagaReplyRequested", {"reply_type": "reply.order.approved"}),
    ]))
    assert state["status"] == "APPROVED" and state["version"] == 3


@pytest.mark.parametrize("reject, expected_status, saga_status, payment_status", [
    (False, "APPROVED", "COMPLETED", "AUTHORIZED"),
    (True, "CANCELLED", "COMPENSATED", "VOIDED"),
])
def test_end_to_end_saga_flow_without_broker_or_database(reject, expected_status,
                                                           saga_status, payment_status):
    """Exercise the real adapter/application/aggregate/Saga state machine together."""
    stores = {role: FakeEventStore() for role in ("order", "accounting", "kitchen", "orchestrator")}
    state = create_order(stores["order"], {
        "consumer_id": "c", "restaurant_id": "restaurant-1",
        "items": [{"price": 10, "quantity": 2}], "reject_kitchen": reject,
    })
    oid = state["order_id"]
    queue = list(stores["order"].outbox)
    visited = []
    while queue:
        assert len(visited) < 15, "Unexpected Saga message cycle"
        msg = queue.pop(0)
        visited.append(msg["type"])
        kind = msg["type"]
        if kind == "order.created" or kind.startswith("reply."):
            target = "orchestrator"
        elif kind.startswith("command.order."):
            target = "order"
        elif kind.startswith("command.account."):
            target = "accounting"
        elif kind.startswith("command.kitchen."):
            target = "kitchen"
        else:
            raise AssertionError(f"Unexpected message: {kind}")
        previous = len(stores[target].outbox)
        handle_delivery(stores[target], target, msg)
        queue.extend(stores[target].outbox[previous:])
    assert evolve("order", stores["order"].histories[oid])["status"] == expected_status
    assert evolve("orchestrator", stores["orchestrator"].histories[f"saga:{oid}"])["status"] == saga_status
    assert evolve("accounting", stores["accounting"].histories[oid])["status"] == payment_status
    assert any(kind == "command.kitchen.prepare" for kind in visited)
    assert ("command.account.void" in visited) == reject
