from uuid import uuid4

from app.application.ports.inbound.order_use_cases import OrderUseCases
from app.application.ports.outbound.order_repository import OrderRepository
from app.domain.order import Order


class OrderApplicationService(OrderUseCases):
    """Application core: implements the inbound port and depends only on ports/domain."""

    def __init__(self, repository: OrderRepository) -> None:
        self._repository = repository

    def create_order(self, restaurant_id: str, item: str, quantity: int) -> Order:
        if not restaurant_id.strip():
            raise ValueError("restaurant_id is required")
        if not item.strip():
            raise ValueError("item is required")
        if quantity <= 0:
            raise ValueError("quantity must be greater than zero")

        order = Order(
            order_id=str(uuid4()),
            restaurant_id=restaurant_id,
            item=item,
            quantity=quantity,
        )
        return self._repository.save(order)

    def get_order(self, order_id: str) -> Order | None:
        return self._repository.find_by_id(order_id)
