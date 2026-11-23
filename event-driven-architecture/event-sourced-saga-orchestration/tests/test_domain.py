from lab.domain import Decision, evolve, integration_message, message, process


def recorded(types):
    return [{"type": kind, "data": data, "version": index + 1}
            for index, (kind, data) in enumerate(types)]


def test_saga_happy_event_sourced_transitions():
    oid = "order-1"
    state = evolve("orchestrator", [])
    start = message("order.created", oid, {"total": 20, "restaurant_id": "r", "reject": False})
    decision = process("orchestrator", start, state)
    assert [x[0] for x in decision.events] == ["SagaOrchestratorCreated", "SagaCommandRequested"]
    state = evolve("orchestrator", recorded(decision.events))
    assert state["step"] == "AUTHORIZING"
    authorized = message("reply.account.authorized", oid, {"restaurant_id": "r", "reject": False})
    decision2 = process("orchestrator", authorized, state)
    assert decision2.messages[0]["type"] == "command.kitchen.prepare"
    state = evolve("orchestrator", recorded(decision.events + decision2.events))
    accepted = message("reply.kitchen.accepted", oid, {})
    decision3 = process("orchestrator", accepted, state)
    assert decision3.messages[0]["type"] == "command.order.approve"
    state = evolve("orchestrator", recorded(decision.events + decision2.events + decision3.events))
    finish = process("orchestrator", message("reply.order.approved", oid, {}), state)
    state = evolve("orchestrator", recorded(decision.events + decision2.events + decision3.events + finish.events))
    assert state["status"] == "COMPLETED"
    assert process("orchestrator", accepted, state).events == []


def test_saga_kitchen_rejection_triggers_void_before_cancel():
    oid = "order-2"
    events = process("orchestrator", message("order.created", oid,
                      {"total": 20, "restaurant_id": "r", "reject": True}), evolve("orchestrator", [])).events
    state = evolve("orchestrator", recorded(events))
    d = process("orchestrator", message("reply.account.authorized", oid, {"reject": True, "restaurant_id": "r"}), state)
    assert d.messages[0]["data"]["reject"] is True
    events += d.events
    state = evolve("orchestrator", recorded(events))
    d = process("orchestrator", message("reply.kitchen.rejected", oid, {}), state)
    assert d.messages[0]["type"] == "command.account.void"
    events += d.events
    state = evolve("orchestrator", recorded(events))
    d = process("orchestrator", message("reply.account.voided", oid, {}), state)
    assert d.messages[0]["type"] == "command.order.cancel"
    events += d.events
    state = evolve("orchestrator", recorded(events))
    d = process("orchestrator", message("reply.order.cancelled", oid, {}), state)
    assert evolve("orchestrator", recorded(events + d.events))["status"] == "COMPENSATED"


def test_participant_pseudo_event_for_reply_when_no_change():
    cmd = message("command.account.authorize", "order-1", {"amount": 20})
    state = evolve("accounting", [])
    first = process("accounting", cmd, state)
    assert [e[0] for e in first.events] == ["AccountAuthorized", "SagaReplyRequested"]
    state = evolve("accounting", recorded(first.events))
    second = process("accounting", cmd, state)
    assert [e[0] for e in second.events] == ["SagaReplyRequested"]
    assert second.messages[0]["message_id"] == first.messages[0]["message_id"]


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
