"""PostgreSQL adapter for Audit Consumer's independent database."""
import os
from sqlalchemy import create_engine, text


class PostgresAuditRepository:
    def __init__(self, engine=None):
        self.engine = engine or create_engine(
            os.getenv('DATABASE_URL', 'postgresql+psycopg://demo:demo@postgres_audit:5432/audit'),
            pool_pre_ping=True,
        )

    def record_received(self, event_id: str, order_id: str) -> None:
        with self.engine.begin() as conn:
            # Re-deliveries are harmless: event_id is the inbox deduplication key.
            conn.execute(text("""INSERT INTO received_events (event_id, order_id)
                VALUES (:id, :oid) ON CONFLICT (event_id) DO NOTHING"""),
                {'id': event_id, 'oid': order_id})
