"""Thin FastAPI adapter: translate HTTP requests to application use cases."""
from fastapi import APIRouter,HTTPException
from app.domain.models import ConcurrencyError
from app.application.order_service import OrderService
from app.adapters.outbound.sqlalchemy_uow import SqlAlchemyUnitOfWork
from app.adapters.inbound.serialization import order_to_dict
from app.adapters.inbound.schemas import CreateOrderRequest,AddItemToOrderRequest,OrderResponse

router=APIRouter(prefix='/orders',tags=['orders'])
service=OrderService(SqlAlchemyUnitOfWork)

def call(action,*args,missing_status=404,**kwargs):
    try: return action(*args,**kwargs)
    except LookupError as exc: raise HTTPException(missing_status,str(exc)) from exc
    except ConcurrencyError as exc: raise HTTPException(409,str(exc)) from exc
    except ValueError as exc: raise HTTPException(400,str(exc)) from exc

@router.post('',response_model=OrderResponse,summary='Create a new order')
def create_order(payload:CreateOrderRequest):
    items=[i.model_dump() for i in payload.line_items]
    order=call(service.create,payload.consumer_id,payload.restaurant_id,items)
    return order_to_dict(order)

@router.get('/{order_id}',response_model=OrderResponse)
def get_order(order_id:str):
    order=call(service.get,order_id)
    if order is None: raise HTTPException(404,'Order not found')
    return order_to_dict(order)

@router.post('/{order_id}/items',response_model=OrderResponse)
def add_item(order_id:str,payload:AddItemToOrderRequest):
    data=payload.model_dump()
    return order_to_dict(call(service.add_item,order_id,**data))

@router.delete('/{order_id}')
def delete_order(order_id:str): return call(service.delete,order_id)

@router.delete('/{order_id}/items/{menu_item_id}',response_model=OrderResponse)
def delete_item(order_id:str,menu_item_id:str):
    try: return order_to_dict(service.delete_item(order_id,menu_item_id))
    except LookupError as exc: raise HTTPException(404,str(exc)) from exc
    except ConcurrencyError as exc: raise HTTPException(409,str(exc)) from exc
    except ValueError as exc: raise HTTPException(404,str(exc)) from exc
