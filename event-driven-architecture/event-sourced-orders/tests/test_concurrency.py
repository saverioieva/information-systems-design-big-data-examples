"""Concurrency and optimistic locking tests (in-memory persistence).

These tests run with the in-memory persistence backend (eventsourcing.popo)
so they are fast and do not require Postgres.
"""

import os

import pytest
from fastapi.testclient import TestClient
from eventsourcing.persistence import IntegrityError

# Force in-memory backend for these tests.
os.environ.setdefault("PERSISTENCE_MODULE", "eventsourcing.popo")

from app.adapters.outbound.eventsourcing_application import OrderApplication
from app.application.errors import ConcurrencyError  # noqa: E402
from app.domain.models import Order  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def order_app_in_memory() -> OrderApplication:
    """Return a fresh OrderApplication using the in-memory backend."""

    os.environ["PERSISTENCE_MODULE"] = "eventsourcing.popo"
    return OrderApplication()


@pytest.fixture
def api_client() -> TestClient:
    """FastAPI TestClient bound to the in-memory application instance."""

    return TestClient(app)


def test_domain_level_optimistic_locking(order_app_in_memory: OrderApplication) -> None:
    """Two concurrent saves for the same version trigger an IntegrityError."""

    app_es = order_app_in_memory

    order_id = app_es.create_order(
        consumer_id="c-1",
        restaurant_id="r-1",
        items=[
            {
                "menu_item_id": "A",
                "name": "Item A",
                "price": 5.0,
                "quantity": 1,
            }
        ],
    )

    order_v1: Order = app_es.repository.get(order_id)
    order_v2: Order = app_es.repository.get(order_id)

    order_v1.add_item_to_order("B", "Item B", 10.0, 1)
    app_es.save(order_v1)

    order_v2.add_item_to_order("C", "Item C", 20.0, 1)

    with pytest.raises(IntegrityError):
        app_es.save(order_v2)


def test_api_optimistic_locking_conflict(api_client: TestClient) -> None:
    """API-level optimistic locking with expected_version -> HTTP 409 on conflict."""

    client = api_client

    create_payload = {
        "consumer_id": "c-2",
        "restaurant_id": "r-2",
        "line_items": [
            {
                "menu_item_id": "X",
                "name": "Item X",
                "price": 10.0,
                "quantity": 1,
            }
        ],
    }

    r_create = client.post("/orders", json=create_payload)
    assert r_create.status_code == 201, r_create.text
    order = r_create.json()
    order_id = order["id"]
    version = order["row_version"]

    add_item_payload = {
        "menu_item_id": "Y",
        "name": "Item Y",
        "price": 5.0,
        "quantity": 1,
        "expected_version": version,
    }

    r1 = client.post(f"/orders/{order_id}/items", json=add_item_payload)
    assert r1.status_code == 200, r1.text
    data1 = r1.json()
    new_version = data1["row_version"]
    assert new_version > version

    r2 = client.post(f"/orders/{order_id}/items", json=add_item_payload)
    assert r2.status_code == 409
    body = r2.json()
    assert (
        "Version mismatch" in body["detail"]
        or "Optimistic locking failed" in body["detail"]
    )


def test_get_historic_versions(api_client: TestClient) -> None:
    """Check that historic versions are accessible via the REST API."""

    client = api_client

    create_payload = {
        "consumer_id": "c-3",
        "restaurant_id": "r-3",
        "line_items": [
            {
                "menu_item_id": "A",
                "name": "Item A",
                "price": 10.0,
                "quantity": 1,
            }
        ],
    }
    r_create = client.post("/orders", json=create_payload)
    assert r_create.status_code == 201
    o1 = r_create.json()
    order_id = o1["id"]
    v1 = o1["row_version"]
    assert v1 == 1

    add_item_payload = {
        "menu_item_id": "B",
        "name": "Item B",
        "price": 5.0,
        "quantity": 2,
        "expected_version": v1,
    }
    r_add = client.post(f"/orders/{order_id}/items", json=add_item_payload)
    assert r_add.status_code == 200
    o2 = r_add.json()
    v2 = o2["row_version"]
    assert v2 == 2

    r_v1 = client.get(f"/orders/{order_id}/versions/1")
    assert r_v1.status_code == 200
    ov1 = r_v1.json()
    assert len(ov1["line_items"]) == 1
    assert ov1["line_items"][0]["menu_item_id"] == "A"

    r_v2 = client.get(f"/orders/{order_id}/versions/2")
    assert r_v2.status_code == 200
    ov2 = r_v2.json()
    assert len(ov2["line_items"]) == 2
    ids = {li["menu_item_id"] for li in ov2["line_items"]}
    assert ids == {"A", "B"}
