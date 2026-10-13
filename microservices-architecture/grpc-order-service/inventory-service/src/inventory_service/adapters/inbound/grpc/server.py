from concurrent import futures
import os
import time

import grpc
from grpc_reflection.v1alpha import reflection

import inventory_pb2
import inventory_pb2_grpc
from inventory_service.application.ports.inbound.inventory_use_cases import InventoryUseCases
from inventory_service.domain.inventory import Availability


class GrpcInventoryAdapter(inventory_pb2_grpc.InventoryServiceServicer):
    """Inbound adapter: translates Protocol Buffer messages into InventoryUseCases calls."""

    def __init__(self, use_cases: InventoryUseCases) -> None:
        self._use_cases = use_cases

    @staticmethod
    def _availability_reply(result: Availability) -> inventory_pb2.AvailabilityReply:
        return inventory_pb2.AvailabilityReply(
            sku=result.sku,
            requested_quantity=result.requested_quantity,
            available_quantity=result.available_quantity,
            available=result.available,
        )

    def CheckAvailability(self, request, context):
        try:
            result = self._use_cases.check_availability(request.sku, request.quantity)
            return self._availability_reply(result)
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))

    def WatchStock(self, request, context):
        try:
            snapshots = self._use_cases.stock_snapshots(request.sku)
        except ValueError as exc:
            context.abort(grpc.StatusCode.NOT_FOUND, str(exc))

        for quantity in snapshots:
            yield inventory_pb2.StockUpdate(sku=request.sku, available_quantity=quantity)
            time.sleep(0.35)

    def CheckMany(self, request_iterator, context):
        results = []
        available_count = 0
        try:
            for request in request_iterator:
                result = self._use_cases.check_availability(request.sku, request.quantity)
                results.append(self._availability_reply(result))
                if result.available:
                    available_count += 1
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))

        return inventory_pb2.BatchAvailabilityReply(
            checked=len(results),
            available_count=available_count,
            results=results,
        )

    def InventorySession(self, request_iterator, context):
        for command in request_iterator:
            try:
                result = self._use_cases.apply_command(command.sku, command.action, command.quantity)
                yield inventory_pb2.InventoryEvent(
                    sku=result.sku,
                    message=result.message,
                    available_quantity=result.available_quantity,
                )
            except ValueError as exc:
                yield inventory_pb2.InventoryEvent(
                    sku=command.sku,
                    message=str(exc),
                    available_quantity=0,
                )


def create_server(use_cases: InventoryUseCases) -> grpc.Server:
    port = os.getenv("GRPC_PORT", "50051")
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    inventory_pb2_grpc.add_InventoryServiceServicer_to_server(
        GrpcInventoryAdapter(use_cases), server
    )

    service_names = (
        inventory_pb2.DESCRIPTOR.services_by_name["InventoryService"].full_name,
        reflection.SERVICE_NAME,
    )
    reflection.enable_server_reflection(service_names, server)
    server.add_insecure_port(f"[::]:{port}")
    return server


def start_server(use_cases: InventoryUseCases) -> grpc.Server:
    port = os.getenv("GRPC_PORT", "50051")
    server = create_server(use_cases)
    server.start()
    print(f"Inventory gRPC adapter listening on :{port}", flush=True)
    return server


def serve(use_cases: InventoryUseCases) -> None:
    server = start_server(use_cases)
    server.wait_for_termination()
