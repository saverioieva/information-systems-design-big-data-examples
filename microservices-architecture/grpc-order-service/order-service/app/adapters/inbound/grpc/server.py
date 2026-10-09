from concurrent import futures
import os
import time

import grpc
from grpc_reflection.v1alpha import reflection

import order_pb2
import order_pb2_grpc
from app.application.services.order_application_service import OrderApplicationService
from app.domain.order import Order, OrderStatus


STATUS_TO_PROTO = {
    OrderStatus.CREATED: order_pb2.CREATED,
    OrderStatus.ACCEPTED: order_pb2.ACCEPTED,
    OrderStatus.PREPARING: order_pb2.PREPARING,
    OrderStatus.READY: order_pb2.READY,
}


class GrpcOrderAdapter(order_pb2_grpc.OrderServiceServicer):
    """Inbound adapter: translates gRPC messages to application use cases."""

    def __init__(self, use_cases: OrderApplicationService):
        self._use_cases = use_cases

    @staticmethod
    def _reply(order: Order) -> order_pb2.OrderReply:
        return order_pb2.OrderReply(
            order_id=order.order_id,
            restaurant_id=order.restaurant_id,
            item=order.item,
            quantity=order.quantity,
            status=STATUS_TO_PROTO[order.status],
        )

    def CreateOrder(self, request, context):
        try:
            order = self._use_cases.create_order(
                restaurant_id=request.restaurant_id,
                item=request.item,
                quantity=request.quantity,
            )
            return self._reply(order)
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))

    def WatchOrder(self, request, context):
        order = self._use_cases.get_order(request.order_id)
        if order is None:
            context.abort(grpc.StatusCode.NOT_FOUND, "order not found")

        for status in (
            order_pb2.CREATED,
            order_pb2.ACCEPTED,
            order_pb2.PREPARING,
            order_pb2.READY,
        ):
            yield order_pb2.OrderUpdate(order_id=request.order_id, status=status)
            time.sleep(0.35)

    def BulkCreateOrders(self, request_iterator, context):
        ids: list[str] = []
        try:
            for request in request_iterator:
                order = self._use_cases.create_order(
                    restaurant_id=request.restaurant_id,
                    item=request.item,
                    quantity=request.quantity,
                )
                ids.append(order.order_id)
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return order_pb2.BulkCreateReply(created=len(ids), order_ids=ids)

    def OrderConversation(self, request_iterator, context):
        for command in request_iterator:
            order = self._use_cases.get_order(command.order_id)
            if order is None:
                yield order_pb2.OrderEvent(
                    order_id=command.order_id,
                    message="order not found",
                )
                continue
            yield order_pb2.OrderEvent(
                order_id=command.order_id,
                message=f"received action: {command.action}",
            )


def serve(use_cases: OrderApplicationService) -> None:
    port = os.getenv("GRPC_PORT", "50051")
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    order_pb2_grpc.add_OrderServiceServicer_to_server(GrpcOrderAdapter(use_cases), server)

    service_names = (
        order_pb2.DESCRIPTOR.services_by_name["OrderService"].full_name,
        reflection.SERVICE_NAME,
    )
    reflection.enable_server_reflection(service_names, server)

    server.add_insecure_port(f"[::]:{port}")
    server.start()
    print(f"Order gRPC service listening on :{port}", flush=True)
    server.wait_for_termination()
