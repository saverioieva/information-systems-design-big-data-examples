"""SQL adapter: idempotency and outbox in one transaction."""
from uuid import uuid4
from sqlalchemy import Table,Column,String,Boolean,select,insert
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert
from saga_common import engine,metadata,outbox,ensure_outbox_table,ensure_inbox_table,claim_message
from domain.policy import can_order

consumers=Table('consumers',metadata,Column('customer_id',String,primary_key=True),Column('can_order',Boolean,nullable=False))
class PostgresConsumerRepository:
    def initialize(self):
        metadata.create_all(engine,tables=[consumers]);ensure_inbox_table();ensure_outbox_table()
        with Session(engine) as s:
            for cid,ok in [('CUST_1',True),('CUST_2',True),('CUST_INVALID',False)]:
                s.execute(pg_insert(consumers).values(customer_id=cid,can_order=ok).on_conflict_do_nothing(index_elements=[consumers.c.customer_id]))
            s.commit()
    def evaluate_order(self,event,props):
        with Session(engine) as s:
            if claim_message(s,event,props):
                row=s.execute(select(consumers.c.can_order).where(consumers.c.customer_id==event['customerId'])).first()
                allowed=can_order(row[0] if row else False)
                route='consumer.verified' if allowed else 'consumer.verificationFailed'
                payload={'type':'ConsumerVerified' if allowed else 'ConsumerVerificationFailed',
                         'orderId':event['orderId'],'customerId':event['customerId'],'messageId':str(uuid4())}
                s.execute(insert(outbox).values(topic=route,payload=payload,status='PENDING'))
            s.commit()
