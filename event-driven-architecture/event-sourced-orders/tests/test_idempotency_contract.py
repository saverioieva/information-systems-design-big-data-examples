"""Independent tests for the redelivery scenario and message contract."""
import pytest
from app.domain.idempotency import IncomingMessage, rebuild
from app.adapters.outbound.postgres_inbox import DDL


def test_contract_requires_id_and_supported_type():
    with pytest.raises(ValueError):
        IncomingMessage('', 'order-1', 'OrderCreated')
    with pytest.raises(ValueError):
        IncomingMessage('m1', 'order-1', 'OrderDeleted')


def test_replay_is_deterministic():
    events = [
      {'version': 1, 'eventType': 'OrderCreated'},
      {'version': 2, 'eventType': 'OrderApproved'},
    ]
    assert rebuild(events) == 'APPROVED'
    assert rebuild(events[:1]) == 'CREATED'


def test_postgres_inbox_and_events_are_separate_tables():
    assert 'demo_processed_messages' in DDL
    assert 'demo_order_events' in DDL
    assert 'message_id TEXT PRIMARY KEY' in DDL
