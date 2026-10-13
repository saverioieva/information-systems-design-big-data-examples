from inventory_service.application.ports.outbound.inventory_repository import InventoryRepository
from inventory_service.domain.inventory import InventoryItem


class InMemoryInventoryRepository(InventoryRepository):
    """Outbound adapter: simple in-memory inventory for the teaching example."""

    def __init__(self, items: list[InventoryItem] | None = None) -> None:
        self._items = {item.sku: item for item in (items or [])}

    def find_by_sku(self, sku: str) -> InventoryItem | None:
        return self._items.get(sku)

    def save(self, item: InventoryItem) -> InventoryItem:
        self._items[item.sku] = item
        return item
