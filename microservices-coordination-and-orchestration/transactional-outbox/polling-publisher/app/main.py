"""HTTP adapter and composition root; Compose entry points preserved."""
import time
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from app.application.use_cases import OutboxUseCases, PollingRelay
from app.adapters.outbound.postgres_repository import PostgresOutboxRepository
from app.adapters.outbound.rabbitmq_publisher import RabbitPublisher

app=FastAPI(title='Transactional Outbox Demo')
repository=PostgresOutboxRepository()
use_cases=OutboxUseCases(repository)

class NewOrder(BaseModel):
    amount:float=Field(gt=0)

@app.on_event('startup')
def startup(): repository.initialize()

@app.post('/orders',status_code=201)
def create_order(payload:NewOrder): return use_cases.create(payload.amount)

@app.get('/orders/{order_id}')
def get_order(order_id:str):
    order=use_cases.get_order(order_id)
    if order is None: raise HTTPException(404,'Order not found')
    return order

@app.get('/outbox')
def list_outbox(): return use_cases.get_outbox()

def relay():
    repository.initialize()
    while True:
        try:
            publisher=RabbitPublisher()
            runner=PollingRelay(repository,publisher)
            try:
                while True:
                    if not runner.publish_once(): time.sleep(0.5)
            finally:
                publisher.close()
        except Exception as exc:
            print(f'[retry] relay: {exc}',flush=True)
            time.sleep(2)

if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host='0.0.0.0',port=8000)
