from abc import ABC, abstractmethod

from order_service.domain.order import Order


class OrderRepository(ABC):
    """Outbound port required by the application core."""

    @abstractmethod
    def save(self, order: Order) -> Order:
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, order_id: int) -> Order | None:
        raise NotImplementedError
