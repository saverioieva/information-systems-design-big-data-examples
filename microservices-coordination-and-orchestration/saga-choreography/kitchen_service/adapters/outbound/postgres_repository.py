"""Persistence adapter with inbox/outbox atomic changes."""
from uuid import uuid4
from datetime import datetime
from sqlalchemy import Table,Column,String,DateTime,insert,update
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert
from saga_common import engine,metadata,outbox,ensure_outbox_table,ensure_inbox_table,claim_message

tickets=Table('tickets',metadata,Column('order_id',String,primary_key=True),Column('status',String,nullable=False),Column('created_at',DateTime,default=datetime.utcnow))
class PostgresKitchenRepository:
    def initialize(self):
        metadata.create_all(engine,tables=[tickets]);ensure_outbox_table();ensure_inbox_table()
    def apply_event(self,event,props,route,new_state):
        oid=event['orderId']
        with Session(engine) as s:
            if not claim_message(s,event,props):s.commit();return
            if route=='order.created':
                inserted=s.execute(pg_insert(tickets).values(order_id=oid,status=new_state,created_at=datetime.utcnow())
                    .on_conflict_do_nothing(index_elements=[tickets.c.order_id]).returning(tickets.c.order_id)).scalar_one_or_none()
                if inserted:
                    s.execute(insert(outbox).values(topic='kitchen.ticketCreated',
                              payload={'type':'TicketCreated','orderId':oid,'status':new_state,'messageId':str(uuid4())}))
            else:
                s.execute(update(tickets).where(tickets.c.order_id==oid).values(status=new_state))
                if new_state=='REJECTED':
                    s.execute(insert(outbox).values(topic='kitchen.ticketRejected',
                              payload={'type':'TicketRejected','orderId':oid,'status':new_state,'messageId':str(uuid4())}))
            s.commit()
