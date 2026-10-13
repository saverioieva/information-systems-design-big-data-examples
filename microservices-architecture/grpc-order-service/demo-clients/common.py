import os
import sys

import grpc

try:
    import inventory_pb2
    import inventory_pb2_grpc
except ImportError:
    print("Generated gRPC modules not found. Run ./scripts/generate_proto.sh first.", file=sys.stderr)
    raise


def stub():
    target = os.getenv("INVENTORY_GRPC_TARGET", "localhost:50051")
    channel = grpc.insecure_channel(target)
    return channel, inventory_pb2_grpc.InventoryServiceStub(channel)
