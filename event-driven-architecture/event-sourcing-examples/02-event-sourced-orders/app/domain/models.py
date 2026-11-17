from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict, Any, ClassVar

from eventsourcing.domain import Aggregate, event


class OrderState(str, Enum):
    APPROVAL_PENDING = "APPROVAL_PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


@dataclass
class OrderLineItem:
    menu_item_id: str
    name: str
    price: float
    quantity: int

    @property
    def subtotal(self) -> float:
        return self.price * self.quantity


class Order(Aggregate):
    """Event-sourced aggregate root for orders.

    This aggregate keeps:
    - the event-sourcing version ("version"),
    - the aggregate schema version,
    - the latest event schema version applied.
    """

    # These are class-level constants, NOT dataclass fields.
    AGGREGATE_SCHEMA_VERSION: ClassVar[int] = 1
    EVENT_SCHEMA_VERSION: ClassVar[int] = 1

    # Dataclass / Aggregate fields (no defaults here).
    consumer_id: str
    restaurant_id: str
    state: OrderState
    line_items: List[OrderLineItem]
    aggregate_schema_version: int

    @event("Created")
    def __init__(
        self,
        consumer_id: str,
        restaurant_id: str,
        items: List[Dict[str, Any]],
        aggregate_schema_version: Optional[int] = None,
        event_schema_version: Optional[int] = None,
    ) -> None:
        """Creates a new order.

        The event payload is kept JSON-serializable (dicts, primitives),
        and this method reconstructs OrderLineItem instances.
        """
        if not items:
            raise ValueError("Order must have at least one item")

        self.consumer_id = consumer_id
        self.restaurant_id = restaurant_id
        self.state = OrderState.APPROVAL_PENDING

        # Versions that travel with events and state.
        self.aggregate_schema_version = (
            aggregate_schema_version
            if aggregate_schema_version is not None
            else self.AGGREGATE_SCHEMA_VERSION
        )
        self._event_schema_version = (
            event_schema_version
            if event_schema_version is not None
            else self.EVENT_SCHEMA_VERSION
        )

        self.line_items = [
            OrderLineItem(
                menu_item_id=i["menu_item_id"],
                name=i["name"],
                price=float(i["price"]),
                quantity=int(i["quantity"]),
            )
            for i in items
        ]

    @event("ItemAdded")
    def add_item_to_order(
        self,
        menu_item_id: str,
        name: str,
        price: float,
        quantity: int,
        event_schema_version: Optional[int] = None,
    ) -> None:
        if self.state != OrderState.APPROVAL_PENDING:
            raise ValueError("Cannot modify a non-pending order")

        self._event_schema_version = (
            event_schema_version
            if event_schema_version is not None
            else self.EVENT_SCHEMA_VERSION
        )

        for idx, item in enumerate(self.line_items):
            if item.menu_item_id == menu_item_id:
                self.line_items[idx] = OrderLineItem(
                    menu_item_id=menu_item_id,
                    name=name,
                    price=price,
                    quantity=item.quantity + quantity,
                )
                break
        else:
            self.line_items.append(
                OrderLineItem(
                    menu_item_id=menu_item_id,
                    name=name,
                    price=price,
                    quantity=quantity,
                )
            )

    @event("ItemRemoved")
    def remove_item_from_order(
        self,
        menu_item_id: str,
        event_schema_version: Optional[int] = None,
    ) -> None:
        if self.state != OrderState.APPROVAL_PENDING:
            raise ValueError("Cannot modify a non-pending order")

        self._event_schema_version = (
            event_schema_version
            if event_schema_version is not None
            else self.EVENT_SCHEMA_VERSION
        )

        new_items = [li for li in self.line_items if li.menu_item_id != menu_item_id]
        if len(new_items) == len(self.line_items):
            raise ValueError("Line item not found")

        self.line_items = new_items

    @event("OrderApproved")
    def approve(self, event_schema_version: Optional[int] = None) -> None:
        if self.state != OrderState.APPROVAL_PENDING:
            raise ValueError("Order must be pending to be approved")
        self.state = OrderState.APPROVED
        self._event_schema_version = (
            event_schema_version
            if event_schema_version is not None
            else self.EVENT_SCHEMA_VERSION
        )

    @event("OrderCancelled")
    def cancel(self, event_schema_version: Optional[int] = None) -> None:
        if self.state in (OrderState.CANCELLED, OrderState.REJECTED):
            return
        self.state = OrderState.CANCELLED
        self._event_schema_version = (
            event_schema_version
            if event_schema_version is not None
            else self.EVENT_SCHEMA_VERSION
        )

    @event("OrderSchemaUpgraded")
    def upgrade_schema(self, new_aggregate_schema_version: int) -> None:
        """Event used to migrate the aggregate state schema."""
        self.aggregate_schema_version = new_aggregate_schema_version

    @property
    def order_total(self) -> float:
        return sum(li.subtotal for li in self.line_items)

    @property
    def row_version(self) -> Optional[int]:
        """Expose the aggregate version as a row version for optimistic locking."""
        return self.version

    @property
    def state_version(self) -> Optional[int]:
        """Alias that makes it explicit this is the state version of the aggregate."""
        return self.version

    @property
    def event_schema_version(self) -> int:
        """Return the latest event schema version that touched this aggregate."""
        return getattr(self, "_event_schema_version", self.EVENT_SCHEMA_VERSION)
