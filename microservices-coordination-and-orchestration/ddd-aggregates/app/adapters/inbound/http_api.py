"""FastAPI inbound adapter: HTTP -> OrderService -> Order Aggregate Root."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.adapters.inbound.schemas import (
    AddLineRequest, ChangeAddressRequest, ChangeQuantityRequest,
    CreateOrderRequest, OrderResponse,
)
from app.adapters.inbound.serialization import order_to_dict
from app.adapters.outbound.sqlalchemy_uow import SqlAlchemyUnitOfWork
from app.application.order_service import OrderService
from app.domain.models import ConcurrencyError

router = APIRouter(prefix='/orders', tags=['orders'])


def get_order_service() -> OrderService:
    return OrderService(SqlAlchemyUnitOfWork)


def call(action, *args, **kwargs):
    try:
        return action(*args, **kwargs)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ConcurrencyError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post('', response_model=OrderResponse, status_code=201)
def create_order(payload: CreateOrderRequest, service: OrderService = Depends(get_order_service)):
    order = call(
        service.create, payload.consumer_id, payload.restaurant_id,
        [line.model_dump() for line in payload.lines]
    )
    return order_to_dict(order)


@router.get('/{order_id}', response_model=OrderResponse)
def get_order(order_id: str, service: OrderService = Depends(get_order_service)):
    order = call(service.get, order_id)
    if order is None:
        raise HTTPException(404, 'Order not found')
    return order_to_dict(order)


@router.post('/{order_id}/lines', response_model=OrderResponse)
def add_line(order_id: str, payload: AddLineRequest, service: OrderService = Depends(get_order_service)):
    data = payload.model_dump(exclude={'expected_version'})
    return order_to_dict(call(service.add_line, order_id, data, payload.expected_version))


@router.patch('/{order_id}/lines/{line_id}', response_model=OrderResponse)
def change_line_quantity(order_id: str, line_id: str, payload: ChangeQuantityRequest,
                         service: OrderService = Depends(get_order_service)):
    return order_to_dict(call(service.change_quantity,
                              order_id, line_id, payload.quantity, payload.expected_version))


@router.delete('/{order_id}/lines/{line_id}', response_model=OrderResponse)
def remove_line(order_id: str, line_id: str, expected_version: int | None = Query(None),
                service: OrderService = Depends(get_order_service)):
    return order_to_dict(call(service.remove_line, order_id, line_id, expected_version))


@router.put('/{order_id}/address', response_model=OrderResponse)
def change_delivery_address(order_id: str, payload: ChangeAddressRequest,
                            service: OrderService = Depends(get_order_service)):
    return order_to_dict(call(service.change_address,
                              order_id, payload.address.model_dump(), payload.expected_version))


@router.post('/{order_id}/approve', response_model=OrderResponse)
def approve_order(order_id: str, expected_version: int | None = Query(None),
                  service: OrderService = Depends(get_order_service)):
    return order_to_dict(call(service.approve, order_id, expected_version))


@router.post('/{order_id}/cancel', response_model=OrderResponse)
def cancel_order(order_id: str, expected_version: int | None = Query(None),
                 service: OrderService = Depends(get_order_service)):
    return order_to_dict(call(service.cancel, order_id, expected_version))
