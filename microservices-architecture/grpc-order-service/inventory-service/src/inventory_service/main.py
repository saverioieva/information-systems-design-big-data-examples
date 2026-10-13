import os

import uvicorn
from fastapi import FastAPI

from inventory_service.adapters.inbound.grpc.server import start_server
from inventory_service.adapters.inbound.rest.routes import create_router
from inventory_service.adapters.outbound.memory.repository import InMemoryInventoryRepository
from inventory_service.application.services.inventory_application_service import InventoryApplicationService
from inventory_service.domain.inventory import InventoryItem


REST_PORT = int(os.getenv("REST_PORT", "8081"))

# Composition root: one application core, two interchangeable inbound transport adapters.
repository = InMemoryInventoryRepository(
    [
        InventoryItem("pizza", 8),
        InventoryItem("pasta", 3),
        InventoryItem("salad", 12),
    ]
)
use_cases = InventoryApplicationService(repository)

rest_app = FastAPI(
    title="FTGO Inventory REST Adapter",
    description=(
        "REST/JSON inbound adapter exposing the same InventoryUseCases used by the gRPC adapter."
    ),
    version="1.0.0",
)
rest_app.include_router(create_router(use_cases))


def main() -> None:
    grpc_server = start_server(use_cases)
    try:
        print(f"Inventory REST adapter listening on :{REST_PORT}", flush=True)
        uvicorn.run(rest_app, host="0.0.0.0", port=REST_PORT)
    finally:
        grpc_server.stop(grace=3)


if __name__ == "__main__":
    main()
