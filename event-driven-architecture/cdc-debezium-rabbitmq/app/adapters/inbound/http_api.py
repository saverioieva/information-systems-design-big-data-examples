"""FastAPI inbound adapter: delegates application use cases."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


class OrderRequest(BaseModel):
    amount: float = Field(gt=0)


def make_router(service):
    router = APIRouter()

    @router.post('/orders', status_code=201)
    def create_order(payload: OrderRequest):
        return service.create(payload.amount)

    @router.post('/orders/{order_id}/approve')
    def approve_order(order_id: str):
        try:
            return service.approve(order_id)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @router.get('/orders')
    def list_orders():
        return service.store.list_orders()

    @router.get('/outbox')
    def list_outbox():
        return service.store.list_outbox()

    return router
