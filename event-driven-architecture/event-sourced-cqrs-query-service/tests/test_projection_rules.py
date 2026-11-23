import pytest

from lab.projection_rules import changes_for


def test_query_projections_from_three_independent_services():
    projection = {}
    for kind, payload in [
        ("integration.order.created", {"consumer_id": "c", "restaurant_id": "r", "total": 18}),
        ("integration.accounting.authorized", {"order_id": "1", "amount": 18}),
        ("integration.kitchen.accepted", {"order_id": "1", "restaurant_id": "r"}),
        ("integration.order.approved", {"order_id": "1"}),
    ]:
        projection.update(changes_for(kind, payload))
    assert projection == {"consumer_id": "c", "restaurant_id": "r", "total": 18,
                          "order_status": "APPROVED", "payment_status": "AUTHORIZED",
                          "kitchen_status": "ACCEPTED"}


def test_compensation_updates_original_read_model():
    projection = {}
    for kind in ("integration.accounting.authorized", "integration.kitchen.rejected",
                 "integration.accounting.voided", "integration.order.cancelled"):
        projection.update(changes_for(kind, {}))
    assert projection["payment_status"] == "VOIDED"
    assert projection["kitchen_status"] == "REJECTED"
    assert projection["order_status"] == "CANCELLED"


def test_unknown_events_fail_loudly():
    with pytest.raises(ValueError):
        changes_for("integration.unexpected", {})
