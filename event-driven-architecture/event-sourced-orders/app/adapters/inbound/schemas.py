from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field



class OrderLineItemRequest(BaseModel):
    menu_item_id: str
    name: str
    price: Decimal = Field(gt=0)
    quantity: int = Field(gt=0)


class CreateOrderRequest(BaseModel):
    consumer_id: str
    restaurant_id: str
    line_items: List[OrderLineItemRequest]


class AddItemToOrderRequest(BaseModel):
    menu_item_id: str
    name: str
    price: Decimal = Field(gt=0)
    quantity: int = Field(gt=0)
    expected_version: Optional[int] = None


class VersionedCommandRequest(BaseModel):
    expected_version: Optional[int] = None


class OrderLineItemResponse(BaseModel):
    menu_item_id: str
    name: str
    price: Decimal
    quantity: int
    subtotal: Decimal


class OrderResponse(BaseModel):
    id: UUID
    consumer_id: str
    restaurant_id: str
    state: str
    line_items: List[OrderLineItemResponse]
    order_total: Decimal

    # Versioning and schema information for optimistic locking and evolution.
    row_version: Optional[int] = None
    state_version: Optional[int] = None
    aggregate_schema_version: Optional[int] = None
    event_schema_version: Optional[int] = None
