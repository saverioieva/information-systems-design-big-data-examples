from abc import ABC, abstractmethod
from typing import Any


class DependencyProbeUseCases(ABC):
    @abstractmethod
    async def probe_dependency(self, service: str, order_id: str) -> Any:
        raise NotImplementedError
