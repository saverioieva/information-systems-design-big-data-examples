from abc import ABC, abstractmethod

from gateway.domain.models import KitchenTicket


class KitchenGateway(ABC):
    @abstractmethod
    async def get_ticket(self, order_id: str) -> KitchenTicket:
        raise NotImplementedError
