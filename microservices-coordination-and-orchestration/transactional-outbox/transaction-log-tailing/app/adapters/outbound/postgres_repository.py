"""SQL adapter: inserts into orders and outbox_events in one transaction."""
import json
import os
from sqlalchemy import create_engine,text
from app.domain.order import OrderCreated

class PostgresOrderRepository:
    def __init__(self,engine=None):
        self.engine=engine or create_engine(os.getenv('DATABASE_URL','postgresql+psycopg://demo:demo@postgres:5432/orders'),pool_pre_ping=True)
    def save_and_enqueue(self,order:OrderCreated) -> None:
        with self.engine.begin() as conn:
            conn.execute(text("INSERT INTO orders(id,amount,status) VALUES (:id,:amount,'CREATED')"),
                         {'id':order.order_id,'amount':order.amount})
            conn.execute(text("""INSERT INTO outbox_events
                        (event_id,aggregate_type,aggregate_id,event_type,payload)
                        VALUES (:eid,'orders',:oid,'OrderCreated',CAST(:body AS jsonb))"""),
                         {'eid':order.event_id,'oid':order.order_id,'body':json.dumps(order.as_message())})
    def find_order(self,order_id):
        with self.engine.connect() as conn:
            row=conn.execute(text('SELECT id,amount,status FROM orders WHERE id=:id'),{'id':order_id}).mappings().first()
        return {'orderId':row['id'],'amount':float(row['amount']),'status':row['status']} if row else None
    def outbox_rows(self):
        with self.engine.connect() as conn:
            rows=conn.execute(text('SELECT event_id,aggregate_id,event_type,created_at FROM outbox_events ORDER BY created_at,event_id')).mappings().all()
        return [{'eventId':r['event_id'],'orderId':r['aggregate_id'],'type':r['event_type'],'createdAt':r['created_at'].isoformat()} for r in rows]
    def received_rows(self):
        with self.engine.connect() as conn:
            rows=conn.execute(text('SELECT event_id,order_id,received_at FROM received_events ORDER BY received_at,event_id')).mappings().all()
        return [{'eventId':r['event_id'],'orderId':r['order_id'],'receivedAt':r['received_at'].isoformat()} for r in rows]
    def record_received(self,event_id,order_id):
        with self.engine.begin() as conn:
            conn.execute(text('INSERT INTO received_events (event_id,order_id) VALUES (:id,:oid) ON CONFLICT (event_id) DO NOTHING'),{'id':event_id,'oid':order_id})
