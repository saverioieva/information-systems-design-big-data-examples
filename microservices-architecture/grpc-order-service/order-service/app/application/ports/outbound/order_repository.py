from abc import ABC, abstractmethod

from app.domain.order import Order


class OrderRepository(ABC):
    """Outbound port required by the application core."""

    @abstractmethod
    def save(self, order: Order) -> Order:
        raise NotImplementedError

    @abstractmethod
    def find_by_id(self, order_id: str) -> Order | None:
        raise NotImplementedError
