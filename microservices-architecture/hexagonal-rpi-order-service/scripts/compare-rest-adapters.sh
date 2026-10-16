#!/usr/bin/env sh
set -eu

printf '\nFastAPI adapter (port 8000)\n'
curl -sS -i -X POST http://localhost:8000/orders \
  -H 'Content-Type: application/json' \
  -d '{"restaurantId":42,"total":25.50}'

printf '\n\nFlask adapter (port 5000)\n'
curl -sS -i -X POST http://localhost:5000/orders \
  -H 'Content-Type: application/json' \
  -d '{"restaurantId":42,"total":25.50}'

printf '\n'
