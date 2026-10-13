#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

./scripts/generate-openapi-client.sh
docker compose build openapi-generated-client
docker compose run --rm openapi-generated-client
