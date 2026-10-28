"""Inbound FastAPI adapter; the Python WAL relay runs separately."""
from fastapi import FastAPI,HTTPException
from pydantic import BaseModel,Field
from app.application.use_cases import OutboxUseCases
from app.adapters.outbound.postgres_repository import PostgresOrderRepository

app=FastAPI(title='Transaction Log Tailing: Python WAL Relay + RabbitMQ')
service=OutboxUseCases(PostgresOrderRepository())
class OrderRequest(BaseModel):
    amount:float=Field(gt=0)

@app.post('/orders',status_code=201)
def create_order(request:OrderRequest):return service.create(request.amount)

@app.get('/orders/{order_id}')
def get_order(order_id:str):
    found=service.get_order(order_id)
    if not found:raise HTTPException(404,'Order not found')
    return found

@app.get('/outbox')
def outbox():return service.get_outbox()

