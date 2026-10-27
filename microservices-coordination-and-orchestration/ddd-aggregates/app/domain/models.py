
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from uuid import uuid4


class OrderState(str, Enum):
    APPROVAL_PENDING = "APPROVAL_PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class ConcurrencyError(Exception):
    pass


@dataclass(frozen=True)
class OrderCreated:
    """Immutable domain-event notification (NOT an event-sourcing record)."""
    event_id: str
    aggregate_type: str
    aggregate_id: str
    occurred_at: str
    amount: float


@dataclass(frozen=True)
class OrderLineItem:
    menu_item_id: str
    name: str
    price: float
    quantity: int

    def __post_init__(self):
        if self.quantity <= 0:
            raise ValueError("Quantity must be positive")
        if self.price < 0:
            raise ValueError("Price must not be negative")

    @property
    def subtotal(self) -> float:
        return self.price * self.quantity


@dataclass
class Order:
    id: str
    consumer_id: str
    restaurant_id: str
    line_items: List[OrderLineItem] = field(default_factory=list)
    state: OrderState = OrderState.APPROVAL_PENDING
    row_version: Optional[int] = None  # explicit SQL version_id; not PostgreSQL xmin
    # In-memory notifications. The repository does NOT persist them as an event store.
    _pending_events: List[OrderCreated] = field(default_factory=list, repr=False, compare=False)

    @classmethod
    def create(cls, consumer_id: str, restaurant_id: str, items: List[OrderLineItem]):
        if not items:
            raise ValueError("Order must have at least one item")
        if not consumer_id or not restaurant_id:
            raise ValueError("Consumer and restaurant IDs are required")
        order = cls(
            id=str(uuid4()),
            consumer_id=consumer_id,
            restaurant_id=restaurant_id,
            line_items=list(items),
        )
        order._pending_events.append(OrderCreated(
            event_id=str(uuid4()),
            aggregate_type="Order",
            aggregate_id=order.id,
            occurred_at=datetime.now(timezone.utc).isoformat(),
            amount=order.order_total,
        ))
        return order

    def collect_domain_events(self) -> List[OrderCreated]:
        """Return and clear pending events; the application layer owns publishing.

        This is NOT event sourcing: persistence uses the current Order state.
        For durable publishing use a transactional outbox (separate lab).
        """
        events = list(self._pending_events)
        self._pending_events.clear()
        return events

    def add_item_to_order(self, menu_item_id: str, name: str, price: float, quantity: int):
        if self.state != OrderState.APPROVAL_PENDING:
            raise ValueError("Cannot modify a non-pending order")
        if quantity <= 0 or price < 0:
            raise ValueError("Quantity must be positive and price nonnegative")

        for idx, item in enumerate(self.line_items):
            if item.menu_item_id == menu_item_id:
                self.line_items[idx] = OrderLineItem(
                    menu_item_id=menu_item_id,
                    name=name,
                    price=price,
                    quantity=item.quantity + quantity,
                )
                return

        self.line_items.append(
            OrderLineItem(menu_item_id=menu_item_id, name=name, price=price, quantity=quantity)
        )

    def remove_item_from_order(self, menu_item_id: str):
        if self.state != OrderState.APPROVAL_PENDING:
            raise ValueError("Cannot modify a non-pending order")

        new_items = [li for li in self.line_items if li.menu_item_id != menu_item_id]
        if len(new_items) == len(self.line_items):
            raise ValueError("Line item not found")
        self.line_items = new_items

    @property
    def order_total(self) -> float:
        return sum(li.subtotal for li in self.line_items)
