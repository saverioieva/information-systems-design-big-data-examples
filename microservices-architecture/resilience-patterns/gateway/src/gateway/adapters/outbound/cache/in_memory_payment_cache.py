from __future__ import annotations

from copy import deepcopy
from threading import Lock

from gateway.application.ports.outbound.payment_cache import PaymentCache
from gateway.domain.models import Payment


class InMemoryPaymentCache(PaymentCache):
    def __init__(self) -> None:
        self._items: dict[str, Payment] = {}
        self._lock = Lock()

    def get(self, order_id: str) -> Payment | None:
        with self._lock:
            value = self._items.get(order_id)
            return deepcopy(value) if value is not None else None

    def put(self, payment: Payment) -> None:
        with self._lock:
            self._items[payment.order_id] = deepcopy(payment)
