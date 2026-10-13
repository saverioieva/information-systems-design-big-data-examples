from inventory_service.application.ports.inbound.inventory_use_cases import InventoryUseCases
from inventory_service.application.ports.outbound.inventory_repository import InventoryRepository
from inventory_service.domain.inventory import Availability, InventoryActionResult, InventoryItem


class InventoryApplicationService(InventoryUseCases):
    """Application core: implements use cases and depends only on repository abstraction."""

    def __init__(self, repository: InventoryRepository) -> None:
        self._repository = repository

    def check_availability(self, sku: str, quantity: int) -> Availability:
        if not sku.strip():
            raise ValueError("sku is required")
        if quantity <= 0:
            raise ValueError("quantity must be greater than zero")

        item = self._repository.find_by_sku(sku)
        available_quantity = item.available_quantity if item else 0
        return Availability(
            sku=sku,
            requested_quantity=quantity,
            available_quantity=available_quantity,
            available=available_quantity >= quantity,
        )

    def stock_snapshots(self, sku: str) -> list[int]:
        item = self._repository.find_by_sku(sku)
        if item is None:
            raise ValueError("unknown sku")

        # Small deterministic sequence used only to make server streaming visible in the lab.
        q = item.available_quantity
        return [q, max(q - 1, 0), max(q - 2, 0)]

    def apply_command(self, sku: str, action: str, quantity: int) -> InventoryActionResult:
        if quantity <= 0:
            raise ValueError("quantity must be greater than zero")

        current = self._repository.find_by_sku(sku)
        if current is None:
            current = InventoryItem(sku=sku, available_quantity=0)

        action = action.lower().strip()
        if action == "reserve":
            if current.available_quantity < quantity:
                return InventoryActionResult(
                    sku=sku,
                    message="not enough stock",
                    available_quantity=current.available_quantity,
                )
            updated = InventoryItem(sku=sku, available_quantity=current.available_quantity - quantity)
            self._repository.save(updated)
            return InventoryActionResult(sku=sku, message="reserved", available_quantity=updated.available_quantity)

        if action == "release":
            updated = InventoryItem(sku=sku, available_quantity=current.available_quantity + quantity)
            self._repository.save(updated)
            return InventoryActionResult(sku=sku, message="released", available_quantity=updated.available_quantity)

        if action == "check":
            return InventoryActionResult(sku=sku, message="checked", available_quantity=current.available_quantity)

        raise ValueError("action must be check, reserve, or release")
