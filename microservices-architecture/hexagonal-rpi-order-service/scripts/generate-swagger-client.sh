#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
mkdir -p "$ROOT_DIR/generated"

docker run --rm \
  -v "$ROOT_DIR:/local" \
  swaggerapi/swagger-codegen-cli-v3:3.0.52 generate \
  -i /local/openapi/order-api.yaml \
  -l python \
  -o /local/generated/swagger-python-client

echo "Generated client: generated/swagger-python-client"
