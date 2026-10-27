"""Composition root: HTTP input, background relay, RabbitMQ input."""
import os
import threading
import time
from fastapi import FastAPI,HTTPException
from pydantic import BaseModel,Field
from app.application.use_cases import SagaUseCases
from app.adapters.outbound.sqlite_store import SqliteSagaStore
from app.adapters.outbound.rabbitmq_transport import connect,RabbitPublisher
from app.adapters.inbound.rabbitmq_consumer import consume

ROLE=os.getenv('ROLE','orchestrator')
DB_FILE=os.getenv('DB_FILE',f'/data/{ROLE}.db')
store=SqliteSagaStore(ROLE,DB_FILE)
use_cases=SagaUseCases(store,ROLE)
app=FastAPI(title='Create Order Saga — Hexagonal Orchestration')

def relay_loop():
    while True:
        try:
            conn=connect();publisher=RabbitPublisher(conn)
            try:
                while True:
                    row=store.pending()
                    if row is None:
                        conn.sleep(0.25);continue
                    publisher.publish(row)
                    store.mark_sent(row['event_id'])
            finally:
                if conn.is_open:conn.close()
        except Exception as exc:
            print(f'[{ROLE}] relay reconnect: {exc}',flush=True)
            time.sleep(1)

def run_workers():
    store.initialize()
    threading.Thread(target=relay_loop,daemon=True).start()
    consume(ROLE,use_cases)

class NewOrder(BaseModel):
    customerId:str=Field(min_length=1)
    amount:float=Field(gt=0)

@app.on_event('startup')
def on_start():
    store.initialize()
    threading.Thread(target=relay_loop,daemon=True).start()
    threading.Thread(target=consume,args=(ROLE,use_cases),daemon=True).start()

@app.post('/orders',status_code=202)
def place_order(payload:NewOrder):
    return use_cases.place_order(payload.customerId,payload.amount)

@app.get('/orders/{order_id}')
def get_order(order_id:str):
    found=use_cases.get_order(order_id)
    if not found:raise HTTPException(404,'Order not found')
    return found

if __name__=='__main__':run_workers()
