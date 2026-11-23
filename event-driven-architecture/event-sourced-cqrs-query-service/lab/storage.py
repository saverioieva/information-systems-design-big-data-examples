"""Each service owns its PostgreSQL database: Event Store + Inbox + Outbox.

The single local transaction is the correctness boundary. Publishing happens
later and may happen more than once, so the recipient Inbox is mandatory.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Callable
from uuid import uuid4
import os

import psycopg
from psycopg.types.json import Jsonb

from lab.domain import Decision, evolve, integration_message

SCHEMA = """
CREATE TABLE IF NOT EXISTS aggregate_heads (
    aggregate_id TEXT PRIMARY KEY,
    aggregate_type TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS events (
    event_id UUID PRIMARY KEY,
    aggregate_id TEXT NOT NULL,
    aggregate_type TEXT NOT NULL,
    version INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(aggregate_id, version)
);
CREATE INDEX IF NOT EXISTS ix_events_stream ON events(aggregate_id, version);
CREATE TABLE IF NOT EXISTS inbox (
    message_id UUID PRIMARY KEY,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS outbox (
    outbox_id BIGSERIAL PRIMARY KEY,
    message_id UUID UNIQUE NOT NULL,
    routing_key TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_outbox_pending ON outbox(outbox_id) WHERE published_at IS NULL;
"""


class EventStore:
    def __init__(self, url: str | None = None):
        self.url = url or os.environ["DATABASE_URL"]

    @contextmanager
    def connection(self):
        with psycopg.connect(self.url, autocommit=True) as connection:
            yield connection

    def ensure_schema(self) -> None:
        with self.connection() as connection:
            connection.execute(SCHEMA)

    @staticmethod
    def _history(connection, aggregate_id: str) -> list[dict[str, Any]]:
        rows = connection.execute(
            "SELECT event_id, version, event_type, payload FROM events WHERE aggregate_id=%s ORDER BY version",
            (aggregate_id,),
        ).fetchall()
        return [{"event_id": str(eid), "version": version, "type": kind, "data": payload}
                for eid, version, kind, payload in rows]

    def read(self, role: str, aggregate_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        with self.connection() as connection:
            history = self._history(connection, aggregate_id)
        return evolve(role, history), history

    def execute(self, *, role: str, aggregate_type: str, aggregate_id: str,
                message_id: str | None, decide: Callable[[dict[str, Any]], Decision]) -> tuple[dict[str, Any], bool]:
        """Atomic: lock stream, deduplicate delivery, append events and messages."""
        with self.connection() as connection:
            with connection.transaction():
                connection.execute(
                    "INSERT INTO aggregate_heads(aggregate_id, aggregate_type, version) "
                    "VALUES (%s,%s,0) ON CONFLICT DO NOTHING",
                    (aggregate_id, aggregate_type),
                )
                head = connection.execute(
                    "SELECT version FROM aggregate_heads WHERE aggregate_id=%s FOR UPDATE",
                    (aggregate_id,),
                ).fetchone()
                if message_id is not None and connection.execute(
                    "SELECT 1 FROM inbox WHERE message_id=%s", (message_id,),
                ).fetchone():
                    return evolve(role, self._history(connection, aggregate_id)), False
                history = self._history(connection, aggregate_id)
                state = evolve(role, history)
                if int(head[0]) != state["version"]:
                    raise RuntimeError("Event stream version and head version disagree")
                decision = decide(state)
                version = state["version"]
                for kind, payload in decision.events:
                    version += 1
                    event_id = str(uuid4())
                    connection.execute(
                        "INSERT INTO events(event_id,aggregate_id,aggregate_type,version,event_type,payload) "
                        "VALUES (%s,%s,%s,%s,%s,%s)",
                        (event_id, aggregate_id, aggregate_type, version, kind, Jsonb(payload)),
                    )
                    if role != "orchestrator":
                        integration = integration_message(role, kind, aggregate_id, version, event_id, payload)
                        if integration:
                            self._enqueue(connection, integration)
                connection.execute(
                    "UPDATE aggregate_heads SET version=%s WHERE aggregate_id=%s",
                    (version, aggregate_id),
                )
                for outgoing in decision.messages:
                    self._enqueue(connection, outgoing)
                if message_id is not None:
                    connection.execute("INSERT INTO inbox(message_id) VALUES (%s)", (message_id,))
                if decision.events:
                    for kind, payload in decision.events:
                        history.append({"version": state["version"] + 1, "type": kind, "data": payload})
                        state["version"] += 1
                    state = evolve(role, history)
                return state, True

    @staticmethod
    def _enqueue(connection, msg: dict[str, Any]):
        connection.execute(
            "INSERT INTO outbox(message_id,routing_key,payload) VALUES (%s,%s,%s) "
            "ON CONFLICT(message_id) DO NOTHING",
            (msg["message_id"], msg["type"], Jsonb(msg)),
        )

    def send_pending(self, publish: Callable[[str, dict[str, Any]], None], batch: int = 50) -> int:
        """Broker confirmation happens before marking sent; crash => safe redelivery."""
        count = 0
        with self.connection() as connection:
            for _ in range(batch):
                with connection.transaction():
                    row = connection.execute(
                        "SELECT outbox_id,routing_key,payload FROM outbox "
                        "WHERE published_at IS NULL ORDER BY outbox_id "
                        "LIMIT 1 FOR UPDATE SKIP LOCKED",
                    ).fetchone()
                    if row is None:
                        return count
                    outbox_id, routing_key, payload = row
                    publish(routing_key, payload)
                    connection.execute("UPDATE outbox SET published_at=now() WHERE outbox_id=%s", (outbox_id,))
                    count += 1
        return count

    def requeue_integration(self) -> int:
        with self.connection() as connection:
            with connection.transaction():
                cursor = connection.execute(
                    "UPDATE outbox SET published_at=NULL WHERE routing_key LIKE 'integration.%'"
                )
                return cursor.rowcount

    def stats(self) -> dict[str, Any]:
        with self.connection() as connection:
            return {
                "events": connection.execute("SELECT count(*) FROM events").fetchone()[0],
                "inbox": connection.execute("SELECT count(*) FROM inbox").fetchone()[0],
                "outbox_pending": connection.execute(
                    "SELECT count(*) FROM outbox WHERE published_at IS NULL"
                ).fetchone()[0],
            }
