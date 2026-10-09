from app.application.ports.outbound.order_repository import OrderRepository
from app.domain.order import Order


class InMemoryOrderRepository(OrderRepository):
    """Outbound adapter: implements the repository port in memory."""

    def __init__(self) -> None:
        self._orders: dict[str, Order] = {}

    def save(self, order: Order) -> Order:
        self._orders[order.order_id] = order
        return order

    def find_by_id(self, order_id: str) -> Order | None:
        return self._orders.get(order_id)
