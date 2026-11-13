"""SQL adapter: atomic Order change and append-only Outbox INSERT."""
from sqlalchemy import create_engine, text
import json


class PostgresOrderStore:
    def __init__(self, database_url: str):
        self.engine = create_engine(database_url, pool_pre_ping=True)

    @staticmethod
    def insert_intent(connection, event: dict):
        connection.execute(text("""
            INSERT INTO outbox_events(event_id, aggregate_type, aggregate_id, event_type, payload)
            VALUES (:event_id, 'orders', :order_id, :type, CAST(:payload AS jsonb))
        """), {'event_id':event['eventId'], 'order_id':event['orderId'],
                'type':event['type'], 'payload': json.dumps(event)})

    def create(self, order_id, amount, event):
        with self.engine.begin() as c:
            c.execute(text("INSERT INTO orders(id, amount, status) VALUES (:id, :amount, 'CREATED')"),
                      {'id':order_id,'amount':amount})
            self.insert_intent(c, event)

    def approve(self, order_id, event_factory):
        with self.engine.begin() as c:
            row = c.execute(text("""
                UPDATE orders SET status='APPROVED'
                WHERE id=:id AND status='CREATED'
                RETURNING amount
            """), {'id': order_id}).mappings().one_or_none()
            if row is None:
                raise ValueError("Order not found or cannot be approved")
            event = event_factory('OrderApproved',order_id,float(row['amount']),'APPROVED').as_dict()
            self.insert_intent(c,event)
            return event

    def list_orders(self):
        with self.engine.connect() as c:
            rows = c.execute(text('SELECT id, amount, status, created_at FROM orders ORDER BY created_at')).mappings().all()
            return [{'id':r['id'],'amount':float(r['amount']),'status':r['status'],
                     'createdAt':r['created_at'].isoformat()} for r in rows]

    def list_outbox(self):
        with self.engine.connect() as c:
            rows = c.execute(text('SELECT event_id,aggregate_id,event_type,created_at FROM outbox_events ORDER BY created_at')).mappings().all()
            return [{'eventId':r['event_id'],'aggregateId':r['aggregate_id'],
                     'eventType':r['event_type'],'createdAt':r['created_at'].isoformat()} for r in rows]
