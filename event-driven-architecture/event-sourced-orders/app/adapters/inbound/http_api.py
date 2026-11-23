"""Inbound HTTP adapter; maps application exceptions to HTTP responses."""
from uuid import UUID
from fastapi import APIRouter, HTTPException
from app.application.errors import ConcurrencyError, OrderNotFound
from app.application.order_service import OrderService
from app.adapters.inbound.schemas import CreateOrderRequest, AddItemToOrderRequest, VersionedCommandRequest, OrderResponse
from app.adapters.inbound.serialization import order_to_dict


def create_router(service: OrderService):
    router = APIRouter(prefix="/orders", tags=["orders"])

    def respond(operation):
        try:
            return order_to_dict(operation())
        except OrderNotFound as exc:
            raise HTTPException(status_code=404, detail="Order or version not found") from exc
        except ConcurrencyError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("", response_model=OrderResponse, status_code=201)
    def create_order(payload: CreateOrderRequest):
        items = [{"menu_item_id": i.menu_item_id, "name": i.name, "price": float(i.price),
                  "quantity": i.quantity} for i in payload.line_items]
        return respond(lambda: service.create_order(payload.consumer_id, payload.restaurant_id, items))

    @router.post("/{order_id}/items", response_model=OrderResponse)
    def add_item_to_order(order_id: UUID, payload: AddItemToOrderRequest):
        return respond(lambda: service.add_item_to_order(order_id, payload.menu_item_id,
                  payload.name, float(payload.price), payload.quantity, payload.expected_version))

    @router.post("/{order_id}/approve", response_model=OrderResponse)
    def approve_order(order_id: UUID, payload: VersionedCommandRequest | None = None):
        return respond(lambda: service.approve_order(order_id, payload.expected_version if payload else None))

    @router.post("/{order_id}/cancel", response_model=OrderResponse)
    def cancel_order(order_id: UUID, payload: VersionedCommandRequest | None = None):
        return respond(lambda: service.cancel_order(order_id, payload.expected_version if payload else None))

    @router.get("/{order_id}", response_model=OrderResponse)
    def get_order(order_id: UUID):
        return respond(lambda: service.get_order(order_id))

    @router.get("/{order_id}/versions/{version}", response_model=OrderResponse)
    def get_order_version(order_id: UUID, version: int):
        return respond(lambda: service.get_order_version(order_id, version))

    return router
