#!/usr/bin/env sh
set -eu

: "${REPLICAS:=3}"

echo "Rolling update (one-by-one) to the CURRENT image tag used by Compose..."
echo "Replicas: ${REPLICAS}"
echo

TARGET_IMAGE_ID="$(docker image inspect rolling-web:prod --format '{{.Id}}')"

wait_for_healthy_replicas() {
  attempts=0
  while [ "$attempts" -lt 30 ]; do
    total=0
    healthy=0
    for container in $(docker compose ps -q web); do
      total=$((total+1))
      status="$(docker inspect "$container" --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}')"
      if [ "$status" = "healthy" ] || [ "$status" = "running" ]; then
        healthy=$((healthy+1))
      fi
    done
    if [ "$total" -eq "$REPLICAS" ] && [ "$healthy" -eq "$REPLICAS" ]; then
      return 0
    fi
    attempts=$((attempts+1))
    sleep 1
  done
  echo "Timed out while waiting for healthy replacement replicas."
  return 1
}

i=1
while [ "$i" -le "$REPLICAS" ]; do
  echo "Step $i/$REPLICAS - replacing one replica"
  CID=""
  for candidate in $(docker compose ps -q web); do
    RUNNING_IMAGE_ID="$(docker inspect "$candidate" --format '{{.Image}}')"
    if [ "$RUNNING_IMAGE_ID" != "$TARGET_IMAGE_ID" ]; then
      CID="$candidate"
      break
    fi
  done

  if [ -z "$CID" ]; then
    echo "No replicas using the previous image remain."
    break
  fi

  docker rm -f "$CID"

  # --no-recreate ensures existing replicas stay up; only the missing one is created.
  docker compose up -d --no-deps --no-recreate --scale "web=${REPLICAS}" web

  wait_for_healthy_replicas

  echo "Current versions (sample):"
  for j in 1 2 3; do
    curl -s localhost:8080 || true
  done
  echo "-----"
  i=$((i+1))
done

echo "Done."
