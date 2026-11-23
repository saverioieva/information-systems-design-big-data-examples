from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional
from uuid import uuid4

class OrderState(str, Enum):
    APPROVAL_PENDING = "APPROVAL_PENDING"
    APPROVED = "APPROVED"
    CANCELLED = "CANCELLED"

class ConcurrencyError(Exception):
    """Raised when a stale version attempts to overwrite a newer order."""

@dataclass(frozen=True)
class OrderLineItem:
    menu_item_id: str
    name: str
    price: float
    quantity: int

    def __post_init__(self):
        if self.price <= 0 or self.quantity <= 0:
            raise ValueError("Price and quantity must be positive")

    @property
    def subtotal(self) -> float:
        return round(self.price * self.quantity, 2)

@dataclass
class Order:
    id: str
    consumer_id: str
    restaurant_id: str
    line_items: List[OrderLineItem] = field(default_factory=list)
    state: OrderState = OrderState.APPROVAL_PENDING
    row_version: Optional[int] = None

    @classmethod
    def create(cls, consumer_id: str, restaurant_id: str, items: List[OrderLineItem]):
        if not items:
            raise ValueError("Order must have at least one item")
        return cls(id=str(uuid4()), consumer_id=consumer_id, restaurant_id=restaurant_id,
                   line_items=list(items))

    def _require_pending(self):
        if self.state != OrderState.APPROVAL_PENDING:
            raise ValueError("Order must be pending")

    def add_item_to_order(self, menu_item_id: str, name: str, price: float, quantity: int):
        self._require_pending()
        added = OrderLineItem(menu_item_id, name, price, quantity)
        for index, item in enumerate(self.line_items):
            if item.menu_item_id == menu_item_id:
                self.line_items[index] = OrderLineItem(menu_item_id, name, price, item.quantity + quantity)
                return
        self.line_items.append(added)

    def remove_item_from_order(self, menu_item_id: str):
        self._require_pending()
        remaining = [item for item in self.line_items if item.menu_item_id != menu_item_id]
        if len(remaining) == len(self.line_items):
            raise ValueError("Line item not found")
        if not remaining:
            raise ValueError("Order must contain at least one item")
        self.line_items = remaining

    def approve(self):
        self._require_pending()
        self.state = OrderState.APPROVED

    def cancel(self):
        self._require_pending()
        self.state = OrderState.CANCELLED

    @property
    def order_total(self) -> float:
        return round(sum(item.subtotal for item in self.line_items), 2)
