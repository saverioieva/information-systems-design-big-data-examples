# app/api/schemas.py
from typing import List, Optional
from pydantic import BaseModel


class OrderLineItemPayload(BaseModel):
    menu_item_id: str
    name: str
    price: float
    quantity: int


class CreateOrderRequest(BaseModel):
    consumer_id: str
    restaurant_id: str
    line_items: List[OrderLineItemPayload]


class AddItemToOrderRequest(BaseModel):
    expected_version: Optional[int] = None
    menu_item_id: str
    name: str
    price: float
    quantity: int


class OrderLineItemResponse(BaseModel):
    menu_item_id: str
    name: str
    price: float
    quantity: int
    subtotal: float


class OrderResponse(BaseModel):
    id: str
    consumer_id: str
    restaurant_id: str
    state: str
    line_items: List[OrderLineItemResponse]
    order_total: float
    row_version: Optional[int] = None
