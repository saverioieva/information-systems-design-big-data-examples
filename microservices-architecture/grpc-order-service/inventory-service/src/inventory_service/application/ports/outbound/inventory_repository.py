from abc import ABC, abstractmethod

from inventory_service.domain.inventory import InventoryItem


class InventoryRepository(ABC):
    """Outbound persistence port required by the Inventory application core."""

    @abstractmethod
    def find_by_sku(self, sku: str) -> InventoryItem | None:
        raise NotImplementedError

    @abstractmethod
    def save(self, item: InventoryItem) -> InventoryItem:
        raise NotImplementedError
