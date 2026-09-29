# Domain Boundaries and SOLID

## Goal

Keep the quote calculation independent from the way product prices are
retrieved.

The same domain rule can use an in-memory catalog, an HTTP catalog, or a
discount catalog.

## 1. Start with the in-memory catalog

```bash
cd domain-solid
unset CATALOG_BACKEND
docker compose up -d --build
curl -s 'http://localhost:8080/quote?quantity=2'
```

Expected total: `2400` cents.

Stop the HTTP catalog and try again:

```bash
docker compose stop catalog
curl -s 'http://localhost:8080/quote?quantity=2'
```

The request still works because the selected implementation is `MemoryCatalog`.

## 2. Use the HTTP catalog

```bash
docker compose start catalog
export CATALOG_BACKEND=http
docker compose up -d --force-recreate orders
curl -s 'http://localhost:8080/quote?quantity=2'
```

The domain calculation is unchanged, but the price now comes from another
service.

Stop that service:

```bash
docker compose stop catalog
curl -i 'http://localhost:8080/quote?quantity=2'
```

The request returns `503` because the selected adapter depends on the network.

## 3. Use the discount catalog

```bash
export CATALOG_BACKEND=discount
docker compose up -d --force-recreate orders
curl -s 'http://localhost:8080/quote?quantity=2'
```

Expected total: `2000` cents. The `quote()` function is unchanged.

## What to observe

- **SRP:** domain logic, adapters, and HTTP handling have separate responsibilities.
- **OCP:** another catalog implementation can be added without changing `quote()`.
- **LSP:** catalog implementations can replace each other when they preserve the same contract.
- **ISP:** the domain needs only the `price_cents()` operation.
- **DIP:** the domain depends on the catalog abstraction rather than a concrete data source.

## Clean up

```bash
unset CATALOG_BACKEND
docker compose down -v
```
