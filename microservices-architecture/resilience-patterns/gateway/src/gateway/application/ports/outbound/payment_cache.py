from abc import ABC, abstractmethod

from gateway.domain.models import Payment


class PaymentCache(ABC):
    @abstractmethod
    def get(self, order_id: str) -> Payment | None:
        raise NotImplementedError

    @abstractmethod
    def put(self, payment: Payment) -> None:
        raise NotImplementedError
