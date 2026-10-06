from sqlalchemy.orm import Session, sessionmaker

from order_service.application.ports.outbound.order_repository import OrderRepository
from order_service.domain.order import Order
from order_service.adapters.outbound.postgres.models import OrderRow


class PostgresOrderRepository(OrderRepository):
    """Outbound adapter: implements the repository port using PostgreSQL."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def save(self, order: Order) -> Order:
        with self._session_factory() as session:
            row = OrderRow(
                restaurant_id=order.restaurant_id,
                status=order.status,
                total=order.total,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return Order(
                id=row.id,
                restaurant_id=row.restaurant_id,
                status=row.status,
                total=row.total,
            )

    def get_by_id(self, order_id: int) -> Order | None:
        with self._session_factory() as session:
            row = session.get(OrderRow, order_id)
            if row is None:
                return None
            return Order(
                id=row.id,
                restaurant_id=row.restaurant_id,
                status=row.status,
                total=row.total,
            )
