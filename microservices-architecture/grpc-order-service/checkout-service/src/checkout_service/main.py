import os

import grpc
from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from checkout_service.adapters.inbound.rest.routes import create_router
from checkout_service.adapters.outbound.grpc.inventory_client import GrpcInventoryClient
from checkout_service.adapters.outbound.rest.inventory_client import RestInventoryClient
from checkout_service.application.services.checkout_application_service import CheckoutApplicationService


INVENTORY_PROTOCOL = os.getenv("INVENTORY_PROTOCOL", "grpc").lower()
INVENTORY_GRPC_TARGET = os.getenv("INVENTORY_GRPC_TARGET", "inventory-service:50051")
INVENTORY_REST_BASE_URL = os.getenv(
    "INVENTORY_REST_BASE_URL", "http://inventory-service:8081"
)

# Composition root: wire one concrete InventoryGateway adapter to the same core.
if INVENTORY_PROTOCOL == "grpc":
    channel = grpc.insecure_channel(INVENTORY_GRPC_TARGET)
    inventory_gateway = GrpcInventoryClient(channel)
elif INVENTORY_PROTOCOL == "rest":
    inventory_gateway = RestInventoryClient(INVENTORY_REST_BASE_URL)
else:
    raise RuntimeError(
        f"Unsupported INVENTORY_PROTOCOL={INVENTORY_PROTOCOL!r}; use 'grpc' or 'rest'."
    )

checkout_use_cases = CheckoutApplicationService(inventory_gateway)

app = FastAPI(
    title=f"FTGO Checkout API ({INVENTORY_PROTOCOL.upper()} internal adapter)",
    description=(
        "Public REST API. The Checkout core reaches Inventory through the "
        f"{INVENTORY_PROTOCOL.upper()} outbound adapter selected at deployment time."
    ),
    version="1.1.0",
)
app.include_router(create_router(checkout_use_cases))


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(
        content=generate_latest(),
        headers={"Content-Type": CONTENT_TYPE_LATEST},
    )
