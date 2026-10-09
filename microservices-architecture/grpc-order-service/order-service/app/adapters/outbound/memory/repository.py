from app.domain.order import Order


class InMemoryOrderRepository:
    """Simple outbound adapter used to keep the gRPC example focused."""

    def __init__(self):
        self._orders: dict[str, Order] = {}

    def save(self, order: Order) -> Order:
        self._orders[order.order_id] = order
        return order

    def find_by_id(self, order_id: str) -> Order | None:
        return self._orders.get(order_id)
