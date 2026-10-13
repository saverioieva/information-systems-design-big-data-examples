from abc import ABC, abstractmethod

from inventory_service.domain.inventory import Availability, InventoryActionResult


class InventoryUseCases(ABC):
    """Inbound port exposed by the Inventory application core."""

    @abstractmethod
    def check_availability(self, sku: str, quantity: int) -> Availability:
        raise NotImplementedError

    @abstractmethod
    def stock_snapshots(self, sku: str) -> list[int]:
        raise NotImplementedError

    @abstractmethod
    def apply_command(self, sku: str, action: str, quantity: int) -> InventoryActionResult:
        raise NotImplementedError
