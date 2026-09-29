# Failure Isolation

## Goal

Compare two ways of calling an optional recommendation service:

- `fragile` waits for the dependency and propagates its failure;
- `resilient` uses a short timeout and returns a reduced response.

## 1. Start the services

```bash
cd failure-isolation
unset DELAY_SECONDS RESILIENT_TIMEOUT_SECONDS
docker compose up -d --build
```

With a healthy dependency:

```bash
curl -s http://localhost:8080/catalog/fragile
curl -s http://localhost:8080/catalog/resilient
```

Both responses contain the product and its recommendation.

## 2. Make the dependency slow

```bash
export DELAY_SECONDS=2
docker compose up -d --force-recreate recommendations

curl -s -w '\nTime: %{time_total}s\n' http://localhost:8080/catalog/fragile
curl -s -w '\nTime: %{time_total}s\n' http://localhost:8080/catalog/resilient
```

The fragile request waits for the dependency. The resilient request stops
waiting after its timeout and returns the product with `"degraded":true`.

## 3. Stop the dependency

```bash
docker compose stop recommendations
curl -i http://localhost:8080/catalog/fragile
curl -i http://localhost:8080/catalog/resilient
curl -i http://localhost:8080/livez
```

The fragile path returns `503`. The resilient path still returns `200` with a
reduced response, and the catalog process remains alive.

## What to observe

- Service separation alone does not isolate failures.
- A timeout limits how long a caller waits for a dependency.
- A fallback is useful only when a reduced result is still valid.

## Clean up

```bash
unset DELAY_SECONDS RESILIENT_TIMEOUT_SECONDS
docker compose down -v
```
