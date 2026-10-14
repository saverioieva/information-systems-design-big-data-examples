from abc import ABC, abstractmethod

from gateway.domain.models import OrderView


class OrderCompositionUseCases(ABC):
    @abstractmethod
    async def compose_order(self, order_id: str) -> OrderView:
        raise NotImplementedError
