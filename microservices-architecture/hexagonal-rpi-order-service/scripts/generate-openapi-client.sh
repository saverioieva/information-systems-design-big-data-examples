#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

mkdir -p generated

docker compose run --rm openapi-generator

echo "Generated client: generated/openapi-python-client"
