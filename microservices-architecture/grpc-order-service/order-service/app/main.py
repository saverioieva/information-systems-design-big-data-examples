from app.adapters.inbound.grpc.server import serve
from app.adapters.outbound.memory.repository import InMemoryOrderRepository
from app.application.services.order_application_service import OrderApplicationService


def main() -> None:
    repository = InMemoryOrderRepository()
    use_cases = OrderApplicationService(repository)
    serve(use_cases)


if __name__ == "__main__":
    main()
