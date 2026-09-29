# API-First and Consumer Compatibility

## Goal

Observe how a consumer reacts to compatible and breaking API changes.

The API exposes one product and `consumer.py` checks the fields used by a
consumer.

## 1. Start the baseline API

```bash
cd api-first
unset API_MODE
docker compose up -d --build
curl -s http://localhost:8080/products/1
docker compose exec api python consumer.py
```

Expected consumer output:

```text
PASS: Notebook costs 1200 cents
```

## 2. Add fields without removing the existing contract

```bash
export API_MODE=additive
docker compose up -d --force-recreate api
curl -s http://localhost:8080/products/1
docker compose exec api python consumer.py
```

The response also contains `currency` and `price_euros`, while the consumer
still works because `price_cents` is unchanged.

## 3. Introduce a breaking change

```bash
export API_MODE=breaking
docker compose up -d --force-recreate api
curl -s http://localhost:8080/products/1
docker compose exec api python consumer.py
```

The API now returns `price` instead of `price_cents`. The consumer fails because
the field it depends on is no longer available.

## What to observe

- The API contract is a boundary between provider and consumer.
- Adding optional information can preserve an existing consumer contract.
- Renaming or changing an existing field can break consumers.

## Clean up

```bash
unset API_MODE
docker compose down -v
```
