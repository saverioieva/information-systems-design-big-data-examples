"""Order Service-owned database: one row per order, not an event store."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from app.domain.order import order_status


def database_path() -> str:
    return os.environ.get("DB_PATH", "/data/orders.sqlite")


def connect() -> sqlite3.Connection:
    path = Path(database_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                consumer_id TEXT NOT NULL,
                item TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                consumer_check TEXT NOT NULL DEFAULT 'PENDING',
                restaurant_check TEXT NOT NULL DEFAULT 'PENDING',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def create_order(order_id: str, consumer_id: str, item: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO orders(id, consumer_id, item) VALUES (?, ?, ?)",
            (order_id, consumer_id, item),
        )


def get_order(order_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    return dict(row) if row is not None else None


def record_validation(order_id: str, source: str, ok: bool) -> dict | None:
    """Idempotent state update; a duplicate result must not change a final decision."""
    if source not in {"consumer", "restaurant"}:
        raise ValueError(f"Unknown validation source: {source}")
    column = f"{source}_check"  # source checked against a whitelist above
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        if row is None:
            return None
        if row[column] == "PENDING":
            conn.execute(
                f"UPDATE orders SET {column} = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                ("PASS" if ok else "FAIL", order_id),
            )
        row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        checks = (row["consumer_check"], row["restaurant_check"])
        status = order_status(*checks)
        conn.execute(
            "UPDATE orders SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, order_id),
        )
        row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        return dict(row)


class SqliteOrderRepository:
    """SQLite adapter implementing OrderRepository."""
    initialize = staticmethod(init_db)
    create = staticmethod(create_order)
    get = staticmethod(get_order)
    record_validation = staticmethod(record_validation)
