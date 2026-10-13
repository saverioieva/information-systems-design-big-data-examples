import grpc

import inventory_pb2
import inventory_pb2_grpc
from checkout_service.application.ports.outbound.inventory_gateway import (
    InventoryAvailability,
    InventoryGateway,
)


class GrpcInventoryClient(InventoryGateway):
    """Outbound adapter: InventoryGateway -> generated gRPC client stub."""

    def __init__(self, channel: grpc.Channel) -> None:
        self._stub = inventory_pb2_grpc.InventoryServiceStub(channel)

    def check_availability(self, sku: str, quantity: int) -> InventoryAvailability:
        try:
            reply = self._stub.CheckAvailability(
                inventory_pb2.CheckAvailabilityRequest(sku=sku, quantity=quantity),
                timeout=3,
            )
        except grpc.RpcError as exc:
            detail = exc.details() or "inventory gRPC call failed"
            raise RuntimeError(detail) from exc

        return InventoryAvailability(
            sku=reply.sku,
            requested_quantity=reply.requested_quantity,
            available_quantity=reply.available_quantity,
            available=reply.available,
        )
