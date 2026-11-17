"""DDD tactical model: entities, value objects, an aggregate root and domain facts.

Only Order exposes business mutations. OrderLine is an immutable *entity
snapshot* whose identity survives changes; Money and Address are immutable
value objects compared by value. Python's conventions are not a security
boundary: the public API and tests enforce the intended aggregate boundary.
"""

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Optional, Sequence
from uuid import uuid4


class ConcurrencyError(Exception):
    """A stale aggregate version was used for an update."""


class OrderState(str, Enum):
    APPROVAL_PENDING = "APPROVAL_PENDING"
    APPROVED = "APPROVED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str = "EUR"

    def __post_init__(self) -> None:
        try:
            amount = Decimal(str(self.amount))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("Invalid monetary amount") from exc
        if not amount.is_finite() or amount < 0 or amount.as_tuple().exponent < -2:
            raise ValueError("Money must be nonnegative with at most two decimals")
        if not isinstance(self.currency, str) or len(self.currency) != 3 or not self.currency.isalpha():
            raise ValueError("Currency must be a three-letter code")
        object.__setattr__(self, "amount", amount.quantize(Decimal("0.01")))
        object.__setattr__(self, "currency", self.currency.upper())

    def __add__(self, other: "Money") -> "Money":
        if not isinstance(other, Money) or self.currency != other.currency:
            raise ValueError("Cannot add amounts in different currencies")
        return Money(self.amount + other.amount, self.currency)

    def times(self, quantity: int) -> "Money":
        if type(quantity) is not int or quantity < 0:
            raise ValueError("Quantity must be a nonnegative integer")
        return Money(self.amount * quantity, self.currency)

    def as_dict(self) -> dict:
        return {"amount": f"{self.amount:.2f}", "currency": self.currency}


@dataclass(frozen=True)
class Address:
    street: str
    city: str
    postal_code: str
    country: str

    def __post_init__(self) -> None:
        for field in ("street", "city", "postal_code", "country"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Address {field} is required")
            object.__setattr__(self, field, value.strip())


@dataclass(frozen=True)
class OrderLineDraft:
    menu_item_id: str
    name: str
    unit_price: Money
    quantity: int

    def __post_init__(self) -> None:
        if not self.menu_item_id or not self.menu_item_id.strip() or not self.name or not self.name.strip():
            raise ValueError("Menu item ID and name are required")
        if not isinstance(self.unit_price, Money):
            raise ValueError("An OrderLine requires a Money value object")
        if type(self.quantity) is not int or self.quantity <= 0:
            raise ValueError("Quantity must be a positive integer")


@dataclass(frozen=True, eq=False)
class OrderLine:
    """Child entity with stable line_id even if its quantity changes."""
    line_id: str
    menu_item_id: str
    name: str
    unit_price: Money
    quantity: int

    @classmethod
    def from_draft(cls, draft: OrderLineDraft) -> "OrderLine":
        return cls(str(uuid4()), draft.menu_item_id, draft.name, draft.unit_price, draft.quantity)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, OrderLine) and self.line_id == other.line_id

    def __hash__(self) -> int:
        return hash(self.line_id)

    @property
    def subtotal(self) -> Money:
        return self.unit_price.times(self.quantity)


@dataclass(frozen=True)
class DomainEvent:
    event_id: str
    aggregate_type: str
    aggregate_id: str
    occurred_at: str


@dataclass(frozen=True)
class OrderCreated(DomainEvent):
    total: str
    currency: str


@dataclass(frozen=True)
class OrderLineAdded(DomainEvent):
    line_id: str
    menu_item_id: str


@dataclass(frozen=True)
class OrderLineQuantityChanged(DomainEvent):
    line_id: str
    quantity: int


@dataclass(frozen=True)
class OrderLineRemoved(DomainEvent):
    line_id: str


@dataclass(frozen=True)
class DeliveryAddressChanged(DomainEvent):
    city: str
    country: str


@dataclass(frozen=True)
class OrderApproved(DomainEvent):
    total: str
    currency: str


@dataclass(frozen=True)
class OrderCancelled(DomainEvent):
    previous_state: str


class Order:
    """The sole entry point for modifying OrderLine entities and Address VO."""

    MIN_APPROVAL_TOTAL = Decimal("15.00")
    MAX_ORDER_TOTAL = Decimal("200.00")

    def __init__(self, *, id: str, consumer_id: str, restaurant_id: str,
                 lines: Sequence[OrderLine], address: Optional[Address] = None,
                 state: OrderState = OrderState.APPROVAL_PENDING,
                 row_version: Optional[int] = None):
        self._id = id
        self._consumer_id = consumer_id
        self._restaurant_id = restaurant_id
        self._lines = list(lines)
        self._address = address
        self._state = OrderState(state)
        self._row_version = row_version
        self._pending_events: list[DomainEvent] = []
        self._check_consistency(self._lines)

    @staticmethod
    def _event(event_type, order_id: str, **data):
        return event_type(
            event_id=str(uuid4()), aggregate_type="Order", aggregate_id=order_id,
            occurred_at=datetime.now(timezone.utc).isoformat(), **data
        )

    @classmethod
    def create(cls, consumer_id: str, restaurant_id: str,
               lines: Sequence[OrderLineDraft], address: Optional[Address] = None) -> "Order":
        if not consumer_id or not consumer_id.strip() or not restaurant_id or not restaurant_id.strip():
            raise ValueError("Consumer and restaurant IDs are required")
        order = cls(
            id=str(uuid4()), consumer_id=consumer_id, restaurant_id=restaurant_id,
            lines=[OrderLine.from_draft(line) for line in lines], address=address
        )
        order._pending_events.append(cls._event(
            OrderCreated, order.id, total=str(order.total.amount), currency=order.total.currency
        ))
        return order

    @classmethod
    def from_persistence(cls, **snapshot) -> "Order":
        """Rehydrate current state in an outbound adapter, never replay events."""
        return cls(**snapshot)

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
    def state(self) -> OrderState:
        return self._state

    @property
    def address(self) -> Optional[Address]:
        return self._address

    @property
    def lines(self) -> tuple[OrderLine, ...]:
        return tuple(self._lines)

    @property
    def row_version(self) -> Optional[int]:
        return self._row_version

    @property
    def total(self) -> Money:
        if not self._lines:
            raise ValueError("Order cannot be empty")
        total = Money(Decimal("0.00"), self._lines[0].unit_price.currency)
        for line in self._lines:
            total = total + line.subtotal
        return total

    def _check_consistency(self, lines: Sequence[OrderLine]) -> None:
        if not lines:
            raise ValueError("Order must have at least one line")
        if len({line.line_id for line in lines}) != len(lines):
            raise ValueError("Duplicate line identity")
        if len({line.menu_item_id for line in lines}) != len(lines):
            raise ValueError("Duplicate menu item; change its quantity through the root")
        if len({line.unit_price.currency for line in lines}) != 1:
            raise ValueError("All lines must have the same currency")
        total = sum((line.subtotal.amount for line in lines), Decimal("0.00"))
        if total > self.MAX_ORDER_TOTAL:
            raise ValueError("Order total exceeds 200.00")

    def _ensure_pending(self) -> None:
        if self._state != OrderState.APPROVAL_PENDING:
            raise ValueError("Only pending orders can be modified")

    def add_line(self, draft: OrderLineDraft) -> None:
        self._ensure_pending()
        candidate = OrderLine.from_draft(draft)
        self._check_consistency([*self._lines, candidate])
        self._lines.append(candidate)
        self._pending_events.append(self._event(
            OrderLineAdded, self.id, line_id=candidate.line_id, menu_item_id=candidate.menu_item_id
        ))

    def change_line_quantity(self, line_id: str, quantity: int) -> None:
        self._ensure_pending()
        if type(quantity) is not int or quantity <= 0:
            raise ValueError("Quantity must be a positive integer")
        candidate = list(self._lines)
        for idx, line in enumerate(candidate):
            if line.line_id == line_id:
                if line.quantity == quantity:
                    return
                candidate[idx] = replace(line, quantity=quantity)  # identity is stable
                self._check_consistency(candidate)
                self._lines = candidate
                self._pending_events.append(self._event(
                    OrderLineQuantityChanged, self.id, line_id=line_id, quantity=quantity
                ))
                return
        raise LookupError("Order line not found")

    def remove_line(self, line_id: str) -> None:
        self._ensure_pending()
        candidate = [line for line in self._lines if line.line_id != line_id]
        if len(candidate) == len(self._lines):
            raise LookupError("Order line not found")
        self._check_consistency(candidate)
        self._lines = candidate
        self._pending_events.append(self._event(OrderLineRemoved, self.id, line_id=line_id))

    def change_delivery_address(self, address: Address) -> None:
        self._ensure_pending()
        if not isinstance(address, Address):
            raise ValueError("A complete Address value object is required")
        if self._address == address:
            return
        self._address = address
        self._pending_events.append(self._event(
            DeliveryAddressChanged, self.id, city=address.city, country=address.country
        ))

    def approve(self) -> None:
        self._ensure_pending()
        if self._address is None:
            raise ValueError("A delivery address is required for approval")
        if self.total.amount < self.MIN_APPROVAL_TOTAL:
            raise ValueError("Order total must be at least 15.00 for approval")
        self._state = OrderState.APPROVED
        self._pending_events.append(self._event(
            OrderApproved, self.id, total=str(self.total.amount), currency=self.total.currency
        ))

    def cancel(self) -> None:
        if self._state == OrderState.CANCELLED:
            raise ValueError("Order is already cancelled")
        previous = self._state.value
        self._state = OrderState.CANCELLED
        self._pending_events.append(self._event(OrderCancelled, self.id, previous_state=previous))

    def collect_domain_events(self) -> list[DomainEvent]:
        events = list(self._pending_events)
        self._pending_events.clear()
        return events
