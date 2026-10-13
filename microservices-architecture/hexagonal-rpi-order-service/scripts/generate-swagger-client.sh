#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

mkdir -p generated

docker compose run --rm swagger-codegen

echo "Generated client: generated/swagger-python-client"
