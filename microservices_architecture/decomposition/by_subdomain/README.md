# Decompose by Subdomain / Bounded Context

## Goal

Implement the same FTGO requirements using two bounded contexts:

- **Restaurant**;
- **Courier**.

Each context has its own service and its own domain model.

## Architecture

```text
Restaurant context          Courier context
       |                           |
       v                           v
+------------------+      +------------------+
| Restaurant       |      | Courier          |
| Service          |      | Service          |
+------------------+      +------------------+
```

The split is derived from the domain language and rules rather than from the high-level `Supplier Management` capability.

## Run

From this directory:

```bash
docker compose up -d --build
```

Inspect the two boundaries:

```bash
curl -s http://localhost:8081/architecture
curl -s http://localhost:8082/architecture
```

## Exercise the Restaurant bounded context

```bash
curl -s -X POST http://localhost:8081/restaurants \
  -H 'Content-Type: application/json' \
  -d '{"name":"La Piazza"}'

curl -s -X PATCH http://localhost:8081/restaurants/1/menu \
  -H 'Content-Type: application/json' \
  -d '{"items":["Pizza","Pasta"]}'
```

Inspect the restaurant model:

```bash
curl -s http://localhost:8081/restaurants/1
```

## Exercise the Courier bounded context

```bash
curl -s -X POST http://localhost:8082/couriers \
  -H 'Content-Type: application/json' \
  -d '{"name":"Alex"}'

curl -s -X PATCH http://localhost:8082/couriers/1/availability \
  -H 'Content-Type: application/json' \
  -d '{"available":true}'
```

Inspect the courier model:

```bash
curl -s http://localhost:8082/couriers/1
```

## What to observe

- There are **two independently deployable services**.
- Each service owns only the vocabulary and rules of its bounded context.
- Restaurant concepts such as `menu` do not leak into the Courier model.
- Courier concepts such as `available` do not leak into the Restaurant model.
- The boundary was selected by asking **“Where do the domain language and rules differ?”**

## Compare with the capability version

The functional requirements are unchanged. What changes is the reasoning used to define the boundary:

- `by_capability/` groups both supplier types under **Supplier Management**;
- `by_subdomain/` separates the **Restaurant** and **Courier** models.

## Clean up

```bash
docker compose down -v
```
