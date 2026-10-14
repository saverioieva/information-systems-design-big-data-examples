from abc import ABC, abstractmethod

from gateway.domain.models import Order


class OrderGateway(ABC):
    @abstractmethod
    async def get_order(self, order_id: str) -> Order:
        raise NotImplementedError
