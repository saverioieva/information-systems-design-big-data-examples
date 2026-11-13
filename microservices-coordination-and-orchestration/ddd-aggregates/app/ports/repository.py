
from abc import ABC, abstractmethod
from typing import Optional
from app.domain.models import Order


class OrderRepository(ABC):

    @abstractmethod
    def add(self, order: Order) -> None:
        ...

    @abstractmethod
    def get(self, order_id: str) -> Optional[Order]:
        ...

    @abstractmethod
    def save(self, order: Order) -> None:
        ...

    @abstractmethod
    def delete(self, order_id: str) -> None:
        ...
