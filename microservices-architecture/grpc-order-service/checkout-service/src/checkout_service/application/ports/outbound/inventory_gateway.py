from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class InventoryAvailability:
    sku: str
    requested_quantity: int
    available_quantity: int
    available: bool


class InventoryGateway(ABC):
    """Outbound port required by Checkout to query Inventory."""

    @abstractmethod
    def check_availability(self, sku: str, quantity: int) -> InventoryAvailability:
        raise NotImplementedError
