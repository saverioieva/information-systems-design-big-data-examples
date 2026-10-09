from abc import ABC, abstractmethod

from app.domain.order import Order


class OrderUseCases(ABC):
    """Inbound port exposed by the application core."""

    @abstractmethod
    def create_order(self, restaurant_id: str, item: str, quantity: int) -> Order:
        raise NotImplementedError

    @abstractmethod
    def get_order(self, order_id: str) -> Order | None:
        raise NotImplementedError
