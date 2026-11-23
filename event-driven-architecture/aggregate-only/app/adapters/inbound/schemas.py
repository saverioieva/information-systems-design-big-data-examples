from typing import List, Optional
from pydantic import BaseModel, Field

class OrderLineItemPayload(BaseModel):
    menu_item_id: str
    name: str
    price: float = Field(gt=0)
    quantity: int = Field(gt=0)

class CreateOrderRequest(BaseModel):
    consumer_id: str
    restaurant_id: str
    line_items: List[OrderLineItemPayload] = Field(min_length=1)

class AddItemToOrderRequest(OrderLineItemPayload):
    expected_version: Optional[int] = None

class VersionedCommandRequest(BaseModel):
    expected_version: Optional[int] = None

class OrderLineItemResponse(OrderLineItemPayload):
    subtotal: float

class OrderResponse(BaseModel):
    id: str
    consumer_id: str
    restaurant_id: str
    state: str
    line_items: List[OrderLineItemResponse]
    order_total: float
    row_version: int
