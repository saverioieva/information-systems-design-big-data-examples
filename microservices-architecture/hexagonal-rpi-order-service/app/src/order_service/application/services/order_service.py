from decimal import Decimal

from order_service.application.ports.inbound.order_use_cases import OrderUseCases
from order_service.application.ports.outbound.order_repository import OrderRepository
from order_service.domain.order import Order


class OrderApplicationService(OrderUseCases):
    """Application core: implements the inbound port and depends only on ports/domain."""

    def __init__(self, repository: OrderRepository) -> None:
        self._repository = repository

    def create_order(self, restaurant_id: int, total: Decimal) -> Order:
        if restaurant_id <= 0:
            raise ValueError("restaurant_id must be positive")
        if total < 0:
            raise ValueError("total cannot be negative")

        order = Order(
            id=None,
            restaurant_id=restaurant_id,
            status="CREATED",
            total=total,
        )
        return self._repository.save(order)

    def get_order(self, order_id: int) -> Order | None:
        if order_id <= 0:
            return None
        return self._repository.get_by_id(order_id)
