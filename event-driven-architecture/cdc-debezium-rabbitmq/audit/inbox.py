"""A tiny independent SQLite Inbox for the teaching audit consumer."""
import json
import os
import sqlite3
from pathlib import Path


class AuditInbox:
    def __init__(self, path: str | None = None):
        self.path = path or os.getenv('AUDIT_DB_PATH', '/audit_data/audit.sqlite3')
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS processed_messages (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                order_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                received_at TEXT NOT NULL DEFAULT (datetime('now'))
            )""")

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def record(self, event: dict) -> bool:
        if not isinstance(event, dict) or not event.get('eventId') or not event.get('type') or not event.get('orderId'):
            raise ValueError('Missing eventId, type or orderId')
        with self.connect() as db:
            result = db.execute("""INSERT OR IGNORE INTO processed_messages
                (event_id, event_type, order_id, payload) VALUES (?, ?, ?, ?)""",
                (event['eventId'], event['type'], event['orderId'], json.dumps(event)))
            return result.rowcount == 1

    def list_records(self):
        with self.connect() as db:
            rows = db.execute("""SELECT event_id, event_type, order_id, received_at
                FROM processed_messages ORDER BY received_at, event_id""").fetchall()
        return [{'eventId':r[0], 'type':r[1], 'orderId':r[2], 'receivedAt':r[3]} for r in rows]
