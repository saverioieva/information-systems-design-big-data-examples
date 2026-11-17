"""FastAPI inbound adapter; it translates HTTP commands into application calls."""
from fastapi import APIRouter, HTTPException
from app.application.order_service import OrderService, OrderNotFound
from app.domain.models import OrderLineItem, ConcurrencyError
from app.adapters.inbound.serialization import order_to_dict
from app.adapters.inbound.schemas import CreateOrderRequest, AddItemToOrderRequest, VersionedCommandRequest, OrderResponse


def create_router(service: OrderService) -> APIRouter:
    router = APIRouter(prefix="/orders", tags=["orders"])

    def respond(operation):
        try:
            return order_to_dict(operation())
        except OrderNotFound as exc:
            raise HTTPException(status_code=404, detail="Order not found") from exc
        except ConcurrencyError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("", response_model=OrderResponse, status_code=201)
    def create_order(payload: CreateOrderRequest):
        return respond(lambda: service.create(
            payload.consumer_id, payload.restaurant_id,
            [OrderLineItem(i.menu_item_id, i.name, i.price, i.quantity) for i in payload.line_items],
        ))

    @router.get("/{order_id}", response_model=OrderResponse)
    def get_order(order_id: str):
        return respond(lambda: service.get(order_id))

    @router.post("/{order_id}/items", response_model=OrderResponse)
    def add_item(order_id: str, payload: AddItemToOrderRequest):
        return respond(lambda: service.add_item(order_id, payload.menu_item_id, payload.name,
                          payload.price, payload.quantity, payload.expected_version))

    @router.post("/{order_id}/approve", response_model=OrderResponse)
    def approve_order(order_id: str, payload: VersionedCommandRequest | None = None):
        return respond(lambda: service.approve(order_id, payload.expected_version if payload else None))

    @router.post("/{order_id}/cancel", response_model=OrderResponse)
    def cancel_order(order_id: str, payload: VersionedCommandRequest | None = None):
        return respond(lambda: service.cancel(order_id, payload.expected_version if payload else None))

    return router
