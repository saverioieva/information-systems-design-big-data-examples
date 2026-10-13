# Decompose by Business Capability

## Goal

Model the FTGO **Supplier Management** capability as one microservice.

The service owns operations for both restaurant and courier suppliers because, at this level of decomposition, they belong to the same business capability.

## Architecture

```text
Clients
   |
   v
+--------------------+
|  Supplier Service  |
|--------------------|
| Restaurant mgmt    |
| Courier mgmt       |
+--------------------+
```


## Implementation note: FastAPI and Pydantic

The service uses FastAPI only to make the example runnable. Classes such as `RestaurantCreate`, `MenuUpdate`, `CourierCreate`, and `AvailabilityUpdate` inherit from Pydantic `BaseModel` because FastAPI uses them to parse and validate incoming JSON requests.

```text
HTTP / JSON
    ↓
Pydantic request DTO
    ↓
FastAPI endpoint
    ↓
example business logic
```

These Pydantic classes are **transport DTOs**, not domain entities and not service-boundary abstractions. This example intentionally avoids Ports and Adapters so that the only design variable under discussion is the **business-capability boundary**.

## Run

From this directory:

```bash
docker compose up -d --build
```

Check the service:

```bash
curl -s http://localhost:8080/architecture
```

The response identifies one service boundary: `Supplier Management`.

## Exercise the restaurant operations

Register a restaurant:

```bash
curl -s -X POST http://localhost:8080/restaurants \
  -H 'Content-Type: application/json' \
  -d '{"name":"La Piazza"}'
```

Update its menu:

```bash
curl -s -X PATCH http://localhost:8080/restaurants/1/menu \
  -H 'Content-Type: application/json' \
  -d '{"items":["Pizza","Pasta"]}'
```

## Exercise the courier operations

Register a courier:

```bash
curl -s -X POST http://localhost:8080/couriers \
  -H 'Content-Type: application/json' \
  -d '{"name":"Alex"}'
```

Update availability:

```bash
curl -s -X PATCH http://localhost:8080/couriers/1/availability \
  -H 'Content-Type: application/json' \
  -d '{"available":true}'
```

Inspect all data owned by the service:

```bash
curl -s http://localhost:8080/suppliers
```

## What to observe

- There is **one deployable unit**.
- Restaurant and courier functions are owned by the same capability-oriented service.
- The boundary was selected by asking **“What business capability owns these operations?”**
- The service can later be split if its sub-capabilities develop different ownership, scaling, or change patterns.

## Clean up

```bash
docker compose down -v
```
