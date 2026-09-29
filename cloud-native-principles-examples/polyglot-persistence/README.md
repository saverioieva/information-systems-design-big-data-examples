# Polyglot Persistence

## Goal

Use two persistence technologies for different purposes:

- SQLite stores the authoritative product price.
- Redis provides a disposable read cache.

## 1. Start the example

```bash
cd polyglot-persistence
unset CACHE_INVALIDATION CACHE_TTL_SECONDS
docker compose up -d --build
```

Read the same product twice:

```bash
curl -s http://localhost:8080/products/1
curl -s http://localhost:8080/products/1
```

The first response comes from the database and the second from the cache.

## 2. Update the product

```bash
curl -s -X PUT http://localhost:8080/products/1 \
  -H 'Content-Type: application/json' \
  -d '{"price_cents":1500}'
curl -s http://localhost:8080/products/1
```

The write invalidates the cached value. The next read returns the new price from
the database.

## 3. Stop the cache

```bash
docker compose stop cache
curl -s http://localhost:8080/products/1
docker compose up -d --force-recreate app
curl -s http://localhost:8080/products/1
docker compose start cache
```

The price is still available because SQLite is the authoritative store and is
persisted on a Docker volume.

## 4. Observe stale cached data

```bash
export CACHE_INVALIDATION=off
docker compose up -d --force-recreate app
curl -s http://localhost:8080/products/1
curl -s -X PUT http://localhost:8080/products/1 \
  -H 'Content-Type: application/json' \
  -d '{"price_cents":1800}'
curl -s http://localhost:8080/products/1
```

With invalidation disabled, Redis can temporarily return the previous value
until the cache entry expires.

## What to observe

- Different data technologies can serve different purposes.
- Losing a cache must not mean losing authoritative data.
- Cache invalidation is part of the consistency design.

## Clean up

```bash
unset CACHE_INVALIDATION CACHE_TTL_SECONDS
docker compose down -v
```
