import os

import grpc
from fastapi import FastAPI

from checkout_service.adapters.inbound.rest.routes import create_router
from checkout_service.adapters.outbound.grpc.inventory_client import GrpcInventoryClient
from checkout_service.application.services.checkout_application_service import CheckoutApplicationService


INVENTORY_GRPC_TARGET = os.getenv("INVENTORY_GRPC_TARGET", "inventory-service:50051")

# Composition root: wire concrete adapters to application ports.
channel = grpc.insecure_channel(INVENTORY_GRPC_TARGET)
inventory_gateway = GrpcInventoryClient(channel)
checkout_use_cases = CheckoutApplicationService(inventory_gateway)

app = FastAPI(
    title="FTGO Checkout API",
    description="Public REST API that collaborates with an internal Inventory Service through gRPC.",
    version="1.0.0",
)
app.include_router(create_router(checkout_use_cases))
