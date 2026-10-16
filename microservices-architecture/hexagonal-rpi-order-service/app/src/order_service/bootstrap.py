from order_service.adapters.outbound.postgres.repository import PostgresOrderRepository
from order_service.application.ports.inbound.order_use_cases import OrderUseCases
from order_service.application.services.order_service import OrderApplicationService
from order_service.infrastructure.database import SessionFactory


def build_order_use_cases() -> OrderUseCases:
    """Composition helper shared by all inbound adapters."""
    repository = PostgresOrderRepository(SessionFactory)
    return OrderApplicationService(repository)
