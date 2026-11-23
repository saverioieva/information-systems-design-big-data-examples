"""RDBMS Inbox + append-only events: one PostgreSQL ACID transaction.

This is an isolated teaching adapter, NOT the eventsourcing library's
`orderapplication_events` table. It demonstrates the same transactional
boundary used by an event-sourced consumer with an SQL event store.
"""
import os
from app.domain.idempotency import IncomingMessage

DDL = """
CREATE TABLE IF NOT EXISTS demo_processed_messages (
  message_id TEXT PRIMARY KEY,
  order_id TEXT NOT NULL,
  received_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS demo_order_events (
  order_id TEXT NOT NULL,
  version INTEGER NOT NULL,
  message_id TEXT NOT NULL UNIQUE,
  event_type TEXT NOT NULL,
  PRIMARY KEY (order_id, version)
);
"""


class PostgresInboxEventStore:
    def __init__(self, dsn: str | None = None):
        self.dsn = dsn or os.getenv('IDEMPOTENCY_POSTGRES_DSN',
                 'postgresql://eventsourcing:eventsourcing@db:5432/orders_es')

    def connect(self):
        import psycopg
        return psycopg.connect(self.dsn)

    def initialize(self):
        with self.connect() as con:
            for statement in DDL.split(";"):
                if statement.strip():
                    con.execute(statement)

    def accept(self, message: IncomingMessage) -> bool:
        with self.connect() as con:
            # Per-order advisory lock prevents two different concurrent
            # messages from selecting the same aggregate version.
            con.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', (message.order_id,))
            row = con.execute('''INSERT INTO demo_processed_messages(message_id, order_id)
                                 VALUES (%s, %s) ON CONFLICT DO NOTHING
                                 RETURNING message_id''',
                              (message.message_id, message.order_id)).fetchone()
            if row is None:
                return False
            version = con.execute('''SELECT COALESCE(MAX(version), 0) + 1
                                     FROM demo_order_events WHERE order_id = %s''',
                                  (message.order_id,)).fetchone()[0]
            con.execute('''INSERT INTO demo_order_events(order_id, version, message_id, event_type)
                           VALUES (%s, %s, %s, %s)''',
                        (message.order_id, version, message.message_id, message.event_type))
            # Connection context commits both inserts or rolls back both.
            return True

    def events(self, order_id: str) -> list[dict]:
        with self.connect() as con:
            rows = con.execute('''SELECT version, message_id, event_type
                                  FROM demo_order_events WHERE order_id=%s ORDER BY version''',
                               (order_id,)).fetchall()
        return [{'version':v, 'messageId':mid, 'eventType':typ} for v,mid,typ in rows]
