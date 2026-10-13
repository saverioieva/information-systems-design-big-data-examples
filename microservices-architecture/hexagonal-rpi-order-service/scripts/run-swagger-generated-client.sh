#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

./scripts/generate-swagger-client.sh
docker compose build swagger-generated-client
docker compose run --rm swagger-generated-client
