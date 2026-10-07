from decimal import Decimal

from order_service.application.ports.outbound.order_repository import OrderRepository
from order_service.application.services.order_service import OrderApplicationService
from order_service.domain.order import Order


class InMemoryOrderRepository(OrderRepository):
    """Test adapter: proves that the application core does not require PostgreSQL."""

    def __init__(self) -> None:
        self._orders: dict[int, Order] = {}
        self._next_id = 1

    def save(self, order: Order) -> Order:
        saved = Order(
            id=self._next_id,
            restaurant_id=order.restaurant_id,
            status=order.status,
            total=order.total,
        )
        self._orders[self._next_id] = saved
        self._next_id += 1
        return saved

    def get_by_id(self, order_id: int) -> Order | None:
        return self._orders.get(order_id)


def test_create_and_get_order_without_framework_or_database() -> None:
    repository = InMemoryOrderRepository()
    service = OrderApplicationService(repository)

    created = service.create_order(restaurant_id=42, total=Decimal("25.50"))
    fetched = service.get_order(created.id or 0)

    assert created.id == 1
    assert created.status == "CREATED"
    assert fetched == created
