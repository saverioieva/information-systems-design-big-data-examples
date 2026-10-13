from abc import ABC, abstractmethod
from decimal import Decimal

from order_service.domain.order import Order


class OrderUseCases(ABC):
    """Inbound port exposed by the application core."""

    @abstractmethod
    def create_order(self, restaurant_id: int, total: Decimal) -> Order:
        raise NotImplementedError

    @abstractmethod
    def get_order(self, order_id: int) -> Order | None:
        raise NotImplementedError
