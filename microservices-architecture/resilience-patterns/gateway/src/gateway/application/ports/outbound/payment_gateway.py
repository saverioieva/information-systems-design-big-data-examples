from abc import ABC, abstractmethod

from gateway.domain.models import Payment


class PaymentGateway(ABC):
    @abstractmethod
    async def get_payment(self, order_id: str) -> Payment:
        raise NotImplementedError
