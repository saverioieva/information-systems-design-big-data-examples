import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "checkout-service" / "src"))

from checkout_service.application.ports.outbound.inventory_gateway import InventoryAvailability, InventoryGateway
from checkout_service.application.services.checkout_application_service import CheckoutApplicationService
from checkout_service.domain.checkout import CheckoutStatus


class FakeInventoryGateway(InventoryGateway):
    def __init__(self, available_quantity: int) -> None:
        self.available_quantity = available_quantity

    def check_availability(self, sku: str, quantity: int) -> InventoryAvailability:
        return InventoryAvailability(
            sku=sku,
            requested_quantity=quantity,
            available_quantity=self.available_quantity,
            available=self.available_quantity >= quantity,
        )


def test_checkout_is_accepted_when_inventory_is_available() -> None:
    service = CheckoutApplicationService(FakeInventoryGateway(8))
    result = service.create_checkout("pizza", 2)
    assert result.status is CheckoutStatus.ACCEPTED
    assert result.available_quantity == 8


def test_checkout_is_rejected_when_inventory_is_insufficient() -> None:
    service = CheckoutApplicationService(FakeInventoryGateway(1))
    result = service.create_checkout("pizza", 2)
    assert result.status is CheckoutStatus.REJECTED
