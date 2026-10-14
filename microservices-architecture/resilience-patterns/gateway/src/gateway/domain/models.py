from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Order:
    order_id: str
    items: list[dict[str, Any]]
    status: str


@dataclass(frozen=True)
class KitchenTicket:
    order_id: str
    ticket_id: str
    status: str
    station: str


@dataclass(frozen=True)
class Delivery:
    order_id: str
    delivery_id: str
    eta_minutes: int
    status: str


@dataclass(frozen=True)
class Payment:
    order_id: str
    payment_id: str
    amount: float
    currency: str
    method: str
    status: str
    source: str | None = None


@dataclass(frozen=True)
class OrderView:
    order: Order
    kitchen: KitchenTicket | None
    delivery: Delivery | None
    payment: Payment | None
    degraded: bool
    missing: list[str] = field(default_factory=list)
    fallbacks: list[str] = field(default_factory=list)
