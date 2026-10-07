from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from order_service.application.ports.inbound.order_use_cases import OrderUseCases
from order_service.domain.order import Order


class CreateOrderRequest(BaseModel):
    restaurantId: int = Field(gt=0)
    total: Decimal = Field(ge=0)


class OrderResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    restaurantId: int
    status: str
    total: Decimal

    @classmethod
    def from_domain(cls, order: Order) -> "OrderResponse":
        assert order.id is not None
        return cls(
            id=order.id,
            restaurantId=order.restaurant_id,
            status=order.status,
            total=order.total,
        )


def build_order_router(use_cases: OrderUseCases) -> APIRouter:
    """Inbound REST adapter: HTTP <-> inbound port translation only."""

    router = APIRouter(prefix="/orders", tags=["orders"])

    @router.post(
        "",
        operation_id="createOrder",
        response_model=OrderResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_order(request: CreateOrderRequest) -> OrderResponse:
        try:
            order = use_cases.create_order(request.restaurantId, request.total)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return OrderResponse.from_domain(order)

    @router.get(
        "/{order_id}",
        operation_id="getOrder",
        response_model=OrderResponse,
    )
    def get_order(order_id: int) -> OrderResponse:
        order = use_cases.get_order(order_id)
        if order is None:
            raise HTTPException(status_code=404, detail="Order not found")
        return OrderResponse.from_domain(order)

    return router
