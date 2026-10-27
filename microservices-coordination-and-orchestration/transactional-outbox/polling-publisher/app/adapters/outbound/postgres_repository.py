"""SQLAlchemy adapter implementing the OutboxRepository port."""
import json
import os
from sqlalchemy import create_engine, text
from app.domain.order import OrderCreated

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id VARCHAR(40) PRIMARY KEY,
    amount NUMERIC NOT NULL,
    status VARCHAR(40) NOT NULL
);
CREATE TABLE IF NOT EXISTS outbox (
    event_id VARCHAR(40) PRIMARY KEY,
    aggregate_id VARCHAR(40) NOT NULL,
    routing_key VARCHAR(120) NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    attempts INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS received_events (
    event_id VARCHAR(40) PRIMARY KEY,
    aggregate_id VARCHAR(40) NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

class PostgresOutboxRepository:
    def __init__(self, engine=None):
        self.engine = engine or create_engine(os.getenv("DATABASE_URL", "postgresql+psycopg://demo:demo@postgres:5432/orders"), pool_pre_ping=True)

    def initialize(self):
        with self.engine.begin() as conn:
            for stmt in SCHEMA.strip().split(';\n'):
                if stmt.strip().rstrip(';'):
                    conn.execute(text(stmt.strip().rstrip(';')))

    def save_order_and_message(self, event: OrderCreated):
        # Atomic local transaction. No broker interaction in this adapter.
        with self.engine.begin() as conn:
            conn.execute(text("INSERT INTO orders(id,amount,status) VALUES (:id,:amount,'CREATED')"),
                         {"id":event.order_id,"amount":event.amount})
            conn.execute(text("""INSERT INTO outbox(event_id,aggregate_id,routing_key,payload)
                                 VALUES (:id,:order,'order.created',CAST(:body AS jsonb))"""),
                         {"id":event.event_id,"order":event.order_id,"body":json.dumps(event.message())})

    def find_order(self, order_id):
        with self.engine.connect() as c:
            row=c.execute(text("SELECT id,amount,status FROM orders WHERE id=:id"), {"id":order_id}).mappings().first()
        return {"orderId":row['id'],"amount":float(row['amount']),"status":row['status']} if row else None

    def pending(self):
        with self.engine.connect() as db:
            row=db.execute(text("""SELECT event_id,routing_key,payload FROM outbox
                                      WHERE status='PENDING' ORDER BY created_at LIMIT 1""")).mappings().first()
        return dict(row) if row else None

    def mark_sent(self, event_id):
        with self.engine.begin() as db:
            db.execute(text("""UPDATE outbox SET status='SENT',attempts=attempts+1,sent_at=NOW()
                               WHERE event_id=:id AND status='PENDING'"""),{"id":event_id})

    def outbox_rows(self):
        with self.engine.connect() as db:
            rows=db.execute(text("SELECT event_id,aggregate_id,status,attempts FROM outbox ORDER BY created_at"))
            return [dict(row) for row in rows.mappings()]

    def received_rows(self):
        with self.engine.connect() as db:
            rows=db.execute(text("SELECT event_id,aggregate_id FROM received_events ORDER BY received_at"))
            return [dict(row) for row in rows.mappings()]

    def record_delivery(self,event_id,order_id):
        with self.engine.begin() as db:
            db.execute(text("""INSERT INTO received_events(event_id,aggregate_id)
                               VALUES (:id,:oid) ON CONFLICT (event_id) DO NOTHING"""),{"id":event_id,"oid":order_id})
