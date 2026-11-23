import os
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
import pytest
from fastapi.testclient import TestClient
from eventsourcing.persistence import IntegrityError

from app.main import app
from app.adapters.outbound.eventsourcing_application import OrderApplication
from app.domain.models import Order


def _build_dsn() -> str:
    host = os.getenv("POSTGRES_HOST", "db")
    port = os.getenv("POSTGRES_PORT", "5432")
    dbname = os.getenv("POSTGRES_DBNAME", "orders_es")
    user = os.getenv("POSTGRES_USER", "eventsourcing")
    password = os.getenv("POSTGRES_PASSWORD", "eventsourcing")
    return f"postgresql://{user}:{password}@{host}:{port}/{dbname}"


def test_create_order_and_persist_events_and_snapshots() -> None:
    """End-to-end integration test with Postgres as event store.

    - Creates an order via FastAPI (OrderApplication + Postgres backend).
    - Produces enough events to trigger at least one snapshot.
    - Verifies via SQL that:
      * events exist in orderapplication_events
      * at least one snapshot exists in orderapplication_snapshots.
    """

    client = TestClient(app)

    create_payload = {
        "consumer_id": "int-c-1",
        "restaurant_id": "int-r-1",
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
    assert r_create.status_code == 201, r_create.text
    order = r_create.json()
    order_id = order["id"]
    version = order["row_version"]
    assert version == 1

    current_version = version
    for i in range(2, 12):  # from 2 to 11 -> 10 events total for this order
        payload = {
            "menu_item_id": f"S{i}",
            "name": f"Snack {i}",
            "price": float(i),
            "quantity": 1,
            "expected_version": current_version,
        }
        r = client.post(f"/orders/{order_id}/items", json=payload)
        assert r.status_code == 200, r.text
        data = r.json()
        current_version = data["row_version"]

    dsn = _build_dsn()
    with psycopg.connect(dsn, row_factory=dict_row) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS cnt "
            "FROM orderapplication_events "
            "WHERE originator_id = %s",
            (UUID(order_id),),
        )
        row = cur.fetchone()
        assert row is not None
        assert row["cnt"] >= 10

        cur.execute(
            "SELECT COUNT(*) AS cnt "
            "FROM orderapplication_snapshots "
            "WHERE originator_id = %s",
            (UUID(order_id),),
        )
        row_s = cur.fetchone()
        assert row_s is not None
        assert row_s["cnt"] >= 1


def test_db_level_optimistic_locking_with_postgres() -> None:
    """Verify DB-level optimistic locking with the Postgres persistence.

    Scenario:
    - Two readers load the same aggregate version.
    - Both apply a change.
    - The first save() succeeds.
    - The second save() raises IntegrityError due to unique constraint on
      (originator_id, originator_version) in the events table.
    """

    assert os.getenv("PERSISTENCE_MODULE") == "eventsourcing.postgres"

    app_pg = OrderApplication()

    order_id = app_pg.create_order(
        consumer_id="lock-c-1",
        restaurant_id="lock-r-1",
        items=[
            {
                "menu_item_id": "A",
                "name": "Item A",
                "price": 5.0,
                "quantity": 1,
            }
        ],
    )

    order_v1: Order = app_pg.repository.get(order_id)
    order_v2: Order = app_pg.repository.get(order_id)

    assert order_v1.version == order_v2.version

    order_v1.add_item_to_order("B", "Item B", 10.0, 1)
    app_pg.save(order_v1)

    order_v2.add_item_to_order("C", "Item C", 20.0, 1)

    with pytest.raises(IntegrityError):
        app_pg.save(order_v2)
