from typing import Protocol

from app.domain.order import Order


class OrderUseCases(Protocol):
    def create_order(self, restaurant_id: str, item: str, quantity: int) -> Order:
        ...

    def get_order(self, order_id: str) -> Order | None:
        ...
