"""Owns SQL transactions, order rows, inbox/outbox."""
from uuid import uuid4
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Table,Column,String,DateTime,Numeric,insert,update,select
from sqlalchemy.orm import Session
from saga_common import engine,metadata,outbox,ensure_outbox_table,ensure_inbox_table,claim_message

orders=Table('orders',metadata,
             Column('order_id',String,primary_key=True),
             Column('customer_id',String,nullable=False),
             Column('amount',Numeric,nullable=False),
             Column('status',String,nullable=False),
             Column('created_at',DateTime,default=datetime.utcnow))

def as_dict(row):
    data=dict(row._mapping)
    if isinstance(data.get('amount'),Decimal):data['amount']=float(data['amount'])
    if isinstance(data.get('created_at'),datetime):data['created_at']=data['created_at'].isoformat()
    return data

class PostgresOrderRepository:
    def initialize(self):
        metadata.create_all(engine,tables=[orders]);ensure_outbox_table();ensure_inbox_table()
    def create(self,customer_id,amount):
        oid=str(uuid4())
        with Session(engine) as s:
            s.execute(insert(orders).values(order_id=oid,customer_id=customer_id,amount=amount,status='APPROVAL_PENDING'))
            event={'type':'OrderCreated','orderId':oid,'customerId':customer_id,'amount':amount,
                   'status':'APPROVAL_PENDING','messageId':str(uuid4())}
            s.execute(insert(outbox).values(topic='order.created',payload=event,status='PENDING'))
            s.commit()
        return oid
    def get(self,oid):
        with Session(engine) as s:
            row=s.execute(select(orders).where(orders.c.order_id==oid)).first()
            return as_dict(row) if row else None
    def list(self):
        with Session(engine) as s:
            return [as_dict(row) for row in s.execute(select(orders).order_by(orders.c.created_at.desc())).all()]
    def apply_result(self,event,props,final_status):
        oid=event['orderId']
        with Session(engine) as s:
            if not claim_message(s,event,props):s.commit();return
            result=s.execute(update(orders).where(orders.c.order_id==oid,orders.c.status=='APPROVAL_PENDING').values(status=final_status))
            if result.rowcount:
                s.execute(insert(outbox).values(topic=f'order.{final_status.lower()}',
                          payload={'type':f'Order{final_status.title()}','orderId':oid,'messageId':str(uuid4())},status='PENDING'))
            s.commit()
