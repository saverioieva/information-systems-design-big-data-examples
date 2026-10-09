import sys
from pathlib import Path

ORDER_SERVICE = Path(__file__).resolve().parents[1] / "order-service"
sys.path.insert(0, str(ORDER_SERVICE))

from app.adapters.outbound.memory.repository import InMemoryOrderRepository
from app.application.services.order_application_service import OrderApplicationService


def test_create_and_get_order():
    service = OrderApplicationService(InMemoryOrderRepository())
    created = service.create_order("restaurant-1", "pizza", 2)

    loaded = service.get_order(created.order_id)

    assert loaded == created
    assert loaded.item == "pizza"
    assert loaded.quantity == 2
