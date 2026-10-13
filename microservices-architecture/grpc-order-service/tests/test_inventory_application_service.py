import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "inventory-service" / "src"))

from inventory_service.adapters.outbound.memory.repository import InMemoryInventoryRepository
from inventory_service.application.ports.inbound.inventory_use_cases import InventoryUseCases
from inventory_service.application.ports.outbound.inventory_repository import InventoryRepository
from inventory_service.application.services.inventory_application_service import InventoryApplicationService
from inventory_service.domain.inventory import InventoryItem


def build_service() -> InventoryApplicationService:
    repository = InMemoryInventoryRepository([InventoryItem("pizza", 8)])
    return InventoryApplicationService(repository)


def test_core_and_repository_follow_declared_ports() -> None:
    repository = InMemoryInventoryRepository([InventoryItem("pizza", 8)])
    service = InventoryApplicationService(repository)
    assert isinstance(repository, InventoryRepository)
    assert isinstance(service, InventoryUseCases)


def test_check_availability() -> None:
    service = build_service()
    result = service.check_availability("pizza", 2)
    assert result.available is True
    assert result.available_quantity == 8


def test_bidirectional_command_logic_is_in_the_core() -> None:
    service = build_service()
    reserved = service.apply_command("pizza", "reserve", 2)
    assert reserved.message == "reserved"
    assert reserved.available_quantity == 6
