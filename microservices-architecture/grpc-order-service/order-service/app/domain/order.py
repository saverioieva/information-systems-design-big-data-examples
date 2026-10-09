from dataclasses import dataclass
from enum import Enum


class OrderStatus(str, Enum):
    CREATED = "CREATED"
    ACCEPTED = "ACCEPTED"
    PREPARING = "PREPARING"
    READY = "READY"


@dataclass(frozen=True)
class Order:
    order_id: str
    restaurant_id: str
    item: str
    quantity: int
    status: OrderStatus = OrderStatus.CREATED
