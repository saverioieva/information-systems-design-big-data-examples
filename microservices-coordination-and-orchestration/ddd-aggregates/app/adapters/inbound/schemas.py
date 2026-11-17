"""HTTP contracts: callers submit value *data*, never domain objects."""

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class StrictPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')


class MoneyPayload(StrictPayload):
    amount: Decimal = Field(ge=0, decimal_places=2)
    currency: str = Field(default='EUR', min_length=3, max_length=3)


class AddressPayload(StrictPayload):
    street: str = Field(min_length=1)
    city: str = Field(min_length=1)
    postal_code: str = Field(min_length=1)
    country: str = Field(min_length=1)


class LinePayload(StrictPayload):
    menu_item_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    unit_price: MoneyPayload
    quantity: int = Field(ge=1)


class CreateOrderRequest(StrictPayload):
    consumer_id: str = Field(min_length=1)
    restaurant_id: str = Field(min_length=1)
    lines: list[LinePayload] = Field(min_length=1)


class AddLineRequest(LinePayload):
    expected_version: Optional[int] = None


class ChangeQuantityRequest(StrictPayload):
    quantity: int = Field(ge=1)
    expected_version: Optional[int] = None


class ChangeAddressRequest(StrictPayload):
    address: AddressPayload
    expected_version: Optional[int] = None


class MoneyResponse(BaseModel):
    amount: str
    currency: str


class AddressResponse(BaseModel):
    street: str
    city: str
    postal_code: str
    country: str


class OrderLineResponse(BaseModel):
    line_id: str
    menu_item_id: str
    name: str
    unit_price: MoneyResponse
    quantity: int
    subtotal: MoneyResponse


class OrderResponse(BaseModel):
    id: str
    consumer_id: str
    restaurant_id: str
    state: str
    address: Optional[AddressResponse]
    lines: list[OrderLineResponse]
    total: MoneyResponse
    row_version: Optional[int]
