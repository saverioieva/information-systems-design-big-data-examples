"""HTTP and RabbitMQ inbound adapters; dependencies composed here."""
import os
import threading
import uvicorn
from fastapi import FastAPI,HTTPException
from pydantic import BaseModel
from saga_common import publish_outbox_forever,run_consumer,flow
from saga_common.routing import QUEUE_BINDINGS
from application.use_cases import OrderUseCases
from adapters.outbound.postgres_repository import PostgresOrderRepository

repo=PostgresOrderRepository();repo.initialize()
service=OrderUseCases(repo)
app=FastAPI(title='Order Service — Hexagonal Choreography')
class CreateOrderIn(BaseModel):
    customerId:str
    amount:float

@app.post('/orders')
def create_order(p: CreateOrderIn):
    result = service.create_order(p.customerId, p.amount)
    flow("order_service", "created", "order.created", result["orderId"])
    return result
@app.get('/orders/{order_id}')
def get_order(order_id:str):
    order=service.order(order_id)
    if not order:raise HTTPException(404,'Order not found')
    return order
@app.get('/orders')
def list_orders():return service.orders()
@app.get('/health')
def health():return {'status':'ok'}


def consume():
    def handler(event, properties, route):
        service.accounting_result(event, route, properties)
    run_consumer("order_service", "order.q", QUEUE_BINDINGS["order.q"], handler)


if __name__ == '__main__':
    threading.Thread(target=publish_outbox_forever, daemon=True).start()
    threading.Thread(target=consume, daemon=True).start()
    uvicorn.run(app, host='0.0.0.0', port=int(os.getenv('PORT', '8000')))
