from typing import Protocol

from app.domain.order import Order


class OrderRepository(Protocol):
    def save(self, order: Order) -> Order:
        ...

    def find_by_id(self, order_id: str) -> Order | None:
        ...
