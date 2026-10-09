import os
from typing import Iterator

import grpc
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

import order_pb2
import order_pb2_grpc


app = FastAPI(
    title="FTGO Public Order API",
    description="External REST API that calls the internal Order Service through gRPC.",
    version="1.0.0",
)

GRPC_TARGET = os.getenv("ORDER_GRPC_TARGET", "order-service:50051")
channel = grpc.insecure_channel(GRPC_TARGET)
stub = order_pb2_grpc.OrderServiceStub(channel)


class CreateOrderBody(BaseModel):
    restaurant_id: str = Field(min_length=1)
    item: str = Field(min_length=1)
    quantity: int = Field(gt=0)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/orders", status_code=201)
def create_order(body: CreateOrderBody):
    try:
        reply = stub.CreateOrder(
            order_pb2.CreateOrderRequest(
                restaurant_id=body.restaurant_id,
                item=body.item,
                quantity=body.quantity,
            )
        )
    except grpc.RpcError as exc:
        raise HTTPException(status_code=502, detail=exc.details()) from exc

    return {
        "orderId": reply.order_id,
        "restaurantId": reply.restaurant_id,
        "item": reply.item,
        "quantity": reply.quantity,
        "status": order_pb2.OrderStatus.Name(reply.status),
    }


@app.get("/orders/{order_id}/updates")
def watch_order(order_id: str):
    """Bridge gRPC server streaming to a simple newline-delimited REST stream."""

    def events() -> Iterator[str]:
        try:
            for update in stub.WatchOrder(order_pb2.WatchOrderRequest(order_id=order_id)):
                yield (
                    '{"orderId":"%s","status":"%s"}\n'
                    % (update.order_id, order_pb2.OrderStatus.Name(update.status))
                )
        except grpc.RpcError as exc:
            yield '{"error":"%s"}\n' % (exc.details() or "gRPC error")

    return StreamingResponse(events(), media_type="application/x-ndjson")
