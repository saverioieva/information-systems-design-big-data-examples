import time

import grpc

import inventory_pb2
import inventory_pb2_grpc
from checkout_service.application.ports.outbound.inventory_gateway import (
    InventoryAvailability,
    InventoryGateway,
)
from checkout_service.metrics import (
    INVENTORY_CLIENT_DURATION,
    INVENTORY_CLIENT_REQUEST_BYTES,
    INVENTORY_CLIENT_REQUESTS,
    INVENTORY_CLIENT_RESPONSE_BYTES,
)


class GrpcInventoryClient(InventoryGateway):
    """Outbound adapter: InventoryGateway -> generated gRPC client stub."""

    protocol = "grpc"

    def __init__(self, channel: grpc.Channel) -> None:
        self._stub = inventory_pb2_grpc.InventoryServiceStub(channel)

    def check_availability(self, sku: str, quantity: int) -> InventoryAvailability:
        request = inventory_pb2.CheckAvailabilityRequest(sku=sku, quantity=quantity)
        INVENTORY_CLIENT_REQUEST_BYTES.labels(protocol=self.protocol).observe(
            len(request.SerializeToString())
        )

        started = time.perf_counter()
        try:
            reply = self._stub.CheckAvailability(request, timeout=3)
        except grpc.RpcError as exc:
            INVENTORY_CLIENT_REQUESTS.labels(protocol=self.protocol, status="error").inc()
            detail = exc.details() or "inventory gRPC call failed"
            raise RuntimeError(detail) from exc
        finally:
            INVENTORY_CLIENT_DURATION.labels(protocol=self.protocol).observe(
                time.perf_counter() - started
            )

        INVENTORY_CLIENT_RESPONSE_BYTES.labels(protocol=self.protocol).observe(
            len(reply.SerializeToString())
        )
        INVENTORY_CLIENT_REQUESTS.labels(protocol=self.protocol, status="success").inc()

        return InventoryAvailability(
            sku=reply.sku,
            requested_quantity=reply.requested_quantity,
            available_quantity=reply.available_quantity,
            available=reply.available,
        )
