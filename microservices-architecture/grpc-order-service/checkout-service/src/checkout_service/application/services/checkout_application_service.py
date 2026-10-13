from checkout_service.application.ports.inbound.checkout_use_cases import CheckoutUseCases
from checkout_service.application.ports.outbound.inventory_gateway import InventoryGateway
from checkout_service.domain.checkout import CheckoutResult, CheckoutStatus


class CheckoutApplicationService(CheckoutUseCases):
    """Application core: depends on the InventoryGateway abstraction, not on gRPC."""

    def __init__(self, inventory: InventoryGateway) -> None:
        self._inventory = inventory

    def create_checkout(self, sku: str, quantity: int) -> CheckoutResult:
        if not sku.strip():
            raise ValueError("sku is required")
        if quantity <= 0:
            raise ValueError("quantity must be greater than zero")

        availability = self._inventory.check_availability(sku, quantity)
        status = CheckoutStatus.ACCEPTED if availability.available else CheckoutStatus.REJECTED
        return CheckoutResult(
            sku=availability.sku,
            quantity=quantity,
            available_quantity=availability.available_quantity,
            status=status,
        )
