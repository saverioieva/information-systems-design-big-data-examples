from inventory_service.adapters.inbound.grpc.server import serve
from inventory_service.adapters.outbound.memory.repository import InMemoryInventoryRepository
from inventory_service.application.services.inventory_application_service import InventoryApplicationService
from inventory_service.domain.inventory import InventoryItem


def main() -> None:
    # Composition root: wire the repository adapter to the application core,
    # then expose the core through the gRPC inbound adapter.
    repository = InMemoryInventoryRepository(
        [
            InventoryItem("pizza", 8),
            InventoryItem("pasta", 3),
            InventoryItem("salad", 12),
        ]
    )
    use_cases = InventoryApplicationService(repository)
    serve(use_cases)


if __name__ == "__main__":
    main()
