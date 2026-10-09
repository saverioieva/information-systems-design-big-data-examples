#!/usr/bin/env sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
OUT="$ROOT/generated"
mkdir -p "$OUT"

python -m grpc_tools.protoc \
  -I "$ROOT/proto" \
  --python_out="$OUT" \
  --grpc_python_out="$OUT" \
  "$ROOT/proto/order.proto"

echo "Generated Python gRPC code in: $OUT"
