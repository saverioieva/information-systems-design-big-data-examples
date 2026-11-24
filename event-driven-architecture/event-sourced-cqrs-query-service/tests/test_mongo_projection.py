"""MongoDB projection tests: run in the lab image with mongomock installed."""
from __future__ import annotations

import mongomock

from lab.read_model import QueryStore


def event(kind, source, version, **data):
    return {"type": kind, "source": source, "version": version,
            "message_id": f"{source}-{version}", "order_id": "o-1", "data": data}


def store():
    return QueryStore(client=mongomock.MongoClient())


def test_history_is_one_document_with_checkpoint_and_idempotent_timeline():
    db = store()
    created = event("integration.order.created", "order", 1, consumer_id="c1",
                    restaurant_id="r1", total=18.0)
    assert db.project(created) is True
    assert db.project(created) is False
    assert db.project(event("integration.accounting.authorized", "accounting", 1)) is True
    assert db.project(event("integration.kitchen.accepted", "kitchen", 1)) is True
    assert db.project(event("integration.order.approved", "order", 2)) is True
    doc = db.history("o-1")
    assert doc["order_status"] == "APPROVED"
    assert doc["payment_status"] == "AUTHORIZED"
    assert doc["kitchen_status"] == "ACCEPTED"
    assert doc["source_versions"] == {"order": 2, "accounting": 1, "kitchen": 1}
    assert len(doc["timeline"]) == 4
    assert db.stats()["orders"] == 1
    assert db.stats()["projected_events"] == 4


def test_late_old_record_cannot_overwrite_new_status():
    db = store()
    assert db.project(event("integration.order.approved", "order", 2))
    assert db.project(event("integration.order.created", "order", 1,
                                consumer_id="c", restaurant_id="r", total=1))
    assert db.find_order("o-1")["order_status"] == "APPROVED"
    assert db.find_order("o-1")["consumer_id"] == "c"
    assert len(db.history("o-1")["timeline"]) == 2  # older event is retained in history


def test_reset_erases_derived_history_only():
    db = store()
    db.project(event("integration.kitchen.rejected", "kitchen", 1))
    assert db.stats()["orders"] == 1
    db.reset()
    assert db.find_order("o-1") is None
    assert db.stats() == {"orders": 0, "projected_events": 0}
