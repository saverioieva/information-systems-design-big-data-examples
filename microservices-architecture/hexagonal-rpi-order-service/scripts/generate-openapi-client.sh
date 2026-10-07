#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
mkdir -p "$ROOT_DIR/generated"

docker run --rm \
  -v "$ROOT_DIR:/local" \
  openapitools/openapi-generator-cli:v7.9.0 generate \
  -i /local/openapi/order-api.yaml \
  -g python \
  -o /local/generated/openapi-python-client

echo "Generated client: generated/openapi-python-client"
