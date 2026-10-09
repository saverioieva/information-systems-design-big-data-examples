import os
import sys

import grpc

# Generated modules are placed in /app/generated in Docker, or ./generated locally.
try:
    import order_pb2
    import order_pb2_grpc
except ImportError as exc:
    print("Generated gRPC modules not found. Run ./scripts/generate_proto.sh first.", file=sys.stderr)
    raise


def stub():
    target = os.getenv("ORDER_GRPC_TARGET", "localhost:50051")
    channel = grpc.insecure_channel(target)
    return channel, order_pb2_grpc.OrderServiceStub(channel)
