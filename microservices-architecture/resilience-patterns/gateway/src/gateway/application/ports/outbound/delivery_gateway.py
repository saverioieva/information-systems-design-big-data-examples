from abc import ABC, abstractmethod

from gateway.domain.models import Delivery


class DeliveryGateway(ABC):
    @abstractmethod
    async def get_delivery(self, order_id: str) -> Delivery:
        raise NotImplementedError
