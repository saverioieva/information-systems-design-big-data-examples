"""DDD tactical model: one Order aggregate protects its own invariants.

Persistence reads the public properties, and reconstructs an Order using the
constructor. State transitions and line-item changes go through root methods.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Sequence
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
    """Immutable domain-event notification raised by the Aggregate Root."""
    event_id: str
    aggregate_type: str
    aggregate_id: str
    occurred_at: str
    amount: float


@dataclass(frozen=True)
class OrderApproved:
    """Business fact recorded by the Order aggregate after a valid approval."""
    event_id: str
    aggregate_type: str
    aggregate_id: str
    occurred_at: str
    amount: float


@dataclass(frozen=True)
class OrderLineItem:
    """Immutable value-like object belonging to the Order aggregate."""
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


class Order:
    """Aggregate Root: no writable public state or line-item collection.

    A tuple view prevents callers from appending, replacing or deleting child
    items without passing through the root's methods. Child items themselves
    are immutable. Python's underscore convention marks the backing fields
    private; it is not an access-control security mechanism.
    """

    def __init__(
        self,
        id: str,
        consumer_id: str,
        restaurant_id: str,
        line_items: Sequence[OrderLineItem] = (),
        state: OrderState = OrderState.APPROVAL_PENDING,
        row_version: Optional[int] = None,
    ):
        self._id = id
        self._consumer_id = consumer_id
        self._restaurant_id = restaurant_id
        self._line_items = list(line_items)  # take ownership; never keep caller's list
        self._state = OrderState(state)
        self.row_version = row_version  # persistence concurrency metadata, not business state
        self._pending_events: List[OrderCreated | OrderApproved] = []

    def __repr__(self) -> str:
        return (
            f"Order(id={self.id!r}, consumer_id={self.consumer_id!r}, "
            f"restaurant_id={self.restaurant_id!r}, line_items={self.line_items!r}, "
            f"state={self.state!r}, row_version={self.row_version!r})"
        )

    @property
    def id(self) -> str:
        return self._id

    @property
    def consumer_id(self) -> str:
        return self._consumer_id

    @property
    def restaurant_id(self) -> str:
        return self._restaurant_id

    @property
    def line_items(self) -> tuple[OrderLineItem, ...]:
        """Read-only snapshot of children (no mutable collection escapes)."""
        return tuple(self._line_items)

    @property
    def state(self) -> OrderState:
        return self._state

    @classmethod
    def create(cls, consumer_id: str, restaurant_id: str, items: Sequence[OrderLineItem]):
        if not items:
            raise ValueError("Order must have at least one item")
        if not consumer_id or not restaurant_id:
            raise ValueError("Consumer and restaurant IDs are required")
        order = cls(
            id=str(uuid4()),
            consumer_id=consumer_id,
            restaurant_id=restaurant_id,
            line_items=items,
        )
        order._pending_events.append(OrderCreated(
            event_id=str(uuid4()),
            aggregate_type="Order",
            aggregate_id=order.id,
            occurred_at=datetime.now(timezone.utc).isoformat(),
            amount=order.order_total,
        ))
        return order

    def approve(self):
        if self._state != OrderState.APPROVAL_PENDING:
            raise ValueError("Only a pending order can be approved")
        if not self._line_items or self.order_total <= 0:
            raise ValueError("An approved order must have a positive total")
        self._state = OrderState.APPROVED
        self._pending_events.append(OrderApproved(
            event_id=str(uuid4()),
            aggregate_type="Order",
            aggregate_id=self.id,
            occurred_at=datetime.now(timezone.utc).isoformat(),
            amount=self.order_total,
        ))

    def collect_domain_events(self) -> List[OrderCreated | OrderApproved]:
        """Return/clear new domain facts for the Unit of Work to persist as intents.

        Current Order state is still persisted by the repository, not an event store.
        """
        events = list(self._pending_events)
        self._pending_events.clear()
        return events

    def add_item_to_order(self, menu_item_id: str, name: str, price: float, quantity: int):
        if self._state != OrderState.APPROVAL_PENDING:
            raise ValueError("Cannot modify a non-pending order")
        # Validate the replacement/new value before touching the aggregate.
        new_item = OrderLineItem(menu_item_id, name, price, quantity)
        for idx, item in enumerate(self._line_items):
            if item.menu_item_id == menu_item_id:
                self._line_items[idx] = OrderLineItem(
                    menu_item_id=menu_item_id,
                    name=name,
                    price=price,
                    quantity=item.quantity + quantity,
                )
                return
        self._line_items.append(new_item)

    def remove_item_from_order(self, menu_item_id: str):
        if self._state != OrderState.APPROVAL_PENDING:
            raise ValueError("Cannot modify a non-pending order")
        remaining = [item for item in self._line_items if item.menu_item_id != menu_item_id]
        if len(remaining) == len(self._line_items):
            raise ValueError("Line item not found")
        if not remaining:
            raise ValueError("Order must have at least one item")
        self._line_items = remaining

    @property
    def order_total(self) -> float:
        return sum(li.subtotal for li in self._line_items)
