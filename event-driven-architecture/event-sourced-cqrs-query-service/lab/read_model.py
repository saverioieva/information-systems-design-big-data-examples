"""Independent CQRS projection owned exclusively by the Order Query Service.

Integration events from three *other* databases arrive at least once. The
projection and inbox/version checkpoints share one local PostgreSQL transaction.
"""
from __future__ import annotations

from typing import Any
import os

import psycopg

from lab.projection_rules import changes_for

SCHEMA = """
CREATE TABLE IF NOT EXISTS order_summary (
    order_id TEXT PRIMARY KEY,
    consumer_id TEXT,
    restaurant_id TEXT,
    total NUMERIC(12,2),
    order_status TEXT NOT NULL DEFAULT 'UNKNOWN',
    payment_status TEXT NOT NULL DEFAULT 'NOT_STARTED',
    kitchen_status TEXT NOT NULL DEFAULT 'NOT_STARTED',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS projection_inbox (
    message_id UUID PRIMARY KEY,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS projection_offsets (
    order_id TEXT NOT NULL,
    source TEXT NOT NULL,
    last_version INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(order_id, source)
);
"""


class QueryStore:
    def __init__(self, url: str | None = None):
        self.url = url or os.environ["DATABASE_URL"]

    def connect(self):
        return psycopg.connect(self.url, autocommit=True)

    def ensure_schema(self):
        with self.connect() as connection:
            connection.execute(SCHEMA)

    def project(self, envelope: dict[str, Any]) -> bool:
        """Deduplicate delivery and reject stale per-source versions atomically."""
        kind = envelope["type"]
        if not kind.startswith("integration."):
            raise ValueError(f"Not an integration event: {kind}")
        oid = envelope["order_id"]
        source = envelope["source"]
        version = int(envelope["version"])
        data = envelope.get("data", {})
        with self.connect() as connection:
            with connection.transaction():
                inserted = connection.execute(
                    "INSERT INTO projection_inbox(message_id) VALUES (%s) ON CONFLICT DO NOTHING RETURNING message_id",
                    (envelope["message_id"],),
                ).fetchone()
                if not inserted:
                    return False
                connection.execute(
                    "INSERT INTO projection_offsets(order_id,source,last_version) "
                    "VALUES (%s,%s,0) ON CONFLICT DO NOTHING", (oid, source),
                )
                existing = connection.execute(
                    "SELECT last_version FROM projection_offsets WHERE order_id=%s AND source=%s FOR UPDATE",
                    (oid, source),
                ).fetchone()[0]
                if version <= existing:
                    return False
                connection.execute("INSERT INTO order_summary(order_id) VALUES (%s) ON CONFLICT DO NOTHING", (oid,))
                changes = changes_for(kind, data)
                if changes:
                    columns = ", ".join(f"{col}=%s" for col in changes)
                    values = list(changes.values())
                    connection.execute(
                        f"UPDATE order_summary SET {columns}, updated_at=now() WHERE order_id=%s",
                        (*values, oid),
                    )
                connection.execute(
                    "UPDATE projection_offsets SET last_version=%s WHERE order_id=%s AND source=%s",
                    (version, oid, source),
                )
                return True

    def find_order(self, oid: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT order_id,consumer_id,restaurant_id,total,order_status,payment_status,"
                "kitchen_status,updated_at FROM order_summary WHERE order_id=%s", (oid,),
            ).fetchone()
            if row is None:
                return None
            offsets = connection.execute(
                "SELECT source,last_version FROM projection_offsets WHERE order_id=%s", (oid,),
            ).fetchall()
        return {"order_id": row[0], "consumer_id": row[1], "restaurant_id": row[2],
                "total": float(row[3]) if row[3] is not None else None,
                "order_status": row[4], "payment_status": row[5],
                "kitchen_status": row[6], "updated_at": row[7].isoformat(),
                "source_versions": dict(offsets)}

    def reset(self) -> None:
        """Demo only: explicitly remove the derived read model, never source events."""
        with self.connect() as connection:
            with connection.transaction():
                connection.execute("TRUNCATE order_summary,projection_inbox,projection_offsets")

    def stats(self) -> dict[str, int]:
        with self.connect() as connection:
            return {"orders": connection.execute("SELECT count(*) FROM order_summary").fetchone()[0],
                    "inbox": connection.execute("SELECT count(*) FROM projection_inbox").fetchone()[0]}
