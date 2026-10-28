"""Audit Service database adapter: no access to Order Service tables."""
import os
from sqlalchemy import create_engine, text


class PostgresAuditRepository:
    def __init__(self, engine=None):
        self.engine = engine or create_engine(
            os.getenv('DATABASE_URL', 'postgresql+psycopg://demo:demo@postgres_audit:5432/audit'),
            pool_pre_ping=True,
        )

    def initialize(self):
        with self.engine.begin() as db:
            db.execute(text("""CREATE TABLE IF NOT EXISTS received_events (
                event_id VARCHAR(40) PRIMARY KEY,
                aggregate_id VARCHAR(40) NOT NULL,
                received_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )"""))

    def record_delivery(self, event_id: str, order_id: str) -> None:
        # Idempotent even when RabbitMQ redelivers after a consumer crash.
        with self.engine.begin() as db:
            db.execute(text("""INSERT INTO received_events(event_id, aggregate_id)
                VALUES (:id, :oid) ON CONFLICT (event_id) DO NOTHING"""),
                {'id': event_id, 'oid': order_id})
