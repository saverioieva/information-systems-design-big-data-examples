# Business Logic, DDD Aggregates and Domain Events — FTGO Order Service

Adapted from last year's `microservices/eventdriven/aggregate_only/` example. This is a **real FastAPI + PostgreSQL + SQLAlchemy** Order Service, plus small pure-Python exercises.

Follows the chapter 4 slides: **Transaction Script vs Domain Model**, **DDD**, **Entity / Value Object**, **Aggregate Root**, **Aggregate Rules**, **Granularity**, **Repository**, and **Domain Events**.

> **Scope of this chapter:** This is **NOT Event Sourcing**. The `orders` and `order_line_items` tables store the **current aggregate state**. Domain Events are short-lived *notifications of significant changes*, not records from which the aggregate is rebuilt. No event store, replay, snapshots, projection rebuilding or event-sourcing infrastructure is introduced.

## Learning objectives

- Distinguish **transaction-script** logic from a **domain model**: invariants belong to an object that controls its state, not to every HTTP handler.
- Identify `Order` as aggregate root and `OrderLineItem` as immutable value-like object.
- See why external references use `consumer_id` and `restaurant_id`, not live cross-service ORM object references.
- Observe local transaction boundaries and detect concurrent updates with an explicit integer version counter.
- Generate an immutable **Domain Event from the aggregate root** and collect it in the application layer; understand why publishing it reliably requires an **outbox** (see `../transactional-outbox/`).

## Architecture

```text
HTTP POST /orders
      |
      v
FastAPI adapter -> OrderRepository interface -> SQLAlchemy adapter -> PostgreSQL
                          |
                          v
                     Order aggregate
              (root + OrderLineItem values)
```

The older example used PostgreSQL's `xmin` system column. This revised lab uses an explicit integer `version_id` column instead, which is easier to explain and works with ordinary optimistic compare-and-swap updates.

## Run

Requirements: Docker Compose, Make and curl. API: <http://localhost:8003/docs>. Adminer: <http://localhost:8083>.

```bash
make up
```

### Exercise 1 — Create an aggregate

```bash
curl -sS -X POST http://localhost:8003/orders \
  -H 'Content-Type: application/json' \
  -d '{"consumer_id":"CUST_1","restaurant_id":"REST_1","line_items":[{"menu_item_id":"PIZZA","name":"Pizza","price":10.0,"quantity":2}]}'
```

From the response note `id`, `state=APPROVAL_PENDING`, `order_total=20.0`, and `row_version`. Use `GET /orders/<id>` for a fresh representation.

### Exercise 2 — Modify through the aggregate root

```bash
curl -sS -X POST http://localhost:8003/orders/<id>/items \
  -H 'Content-Type: application/json' \
  -d '{"menu_item_id":"PIZZA","name":"Pizza","price":10.0,"quantity":1}'
```

The total should become 30.0. The HTTP layer calls the `Order.add_item_to_order()` **domain method**; it does not mutate the database directly.

### Exercise 3 — Invariant validation and value objects

```bash
python -m unittest discover -s tests -v
```

Tests demonstrate nonempty orders, positive quantities, and the prohibition on modifying an approved order. Read `app/domain/models.py` before looking at the adapter.

### Exercise 4 — Domain event without the broker

```bash
python -m examples.domain_events
```

`Order.create()` adds an immutable `OrderCreated` notification (event ID, aggregate type/ID, timestamp, amount) to the aggregate's **in-memory pending events**. The application layer calls `collect_domain_events()` to retrieve and clear them. **There is no event-store table and no event replay.** The API portion of this lab persists only current state; it deliberately does not publish these notifications. The companion `transactional-outbox/` lab shows how a service could persist a delivery intent atomically alongside a local business update.

### Exercise 5 — Optimistic locking

Open two sessions or two API clients that fetch the same order before changing it. The repository's `save()` uses a compare-and-swap update on `version_id`; a stale update raises `ConcurrencyError`, mapped to HTTP 409. The `POST /orders/<id>/items` payload optionally accepts `expected_version`. Fetch the row, then try adding an item with that version twice: the second request should return HTTP 409. Read `app/adapters/outbound/sqlalchemy_repository.py` and discuss why concurrency control is important when many independent actors act on the same aggregate.

**Caveat:** the `expected_version` field is a teaching simplification; a production REST API may use `ETag`/`If-Match`. Monetary values still use `float` for simplicity.

### Code reading order

| File | Role |
|---|---|
| `app/domain/models.py` | Domain objects and invariants |
| `app/domain/repository.py` | Repository abstraction |
| `app/adapters/inbound/http_api.py` | Thin inbound FastAPI adapter |
| `app/adapters/outbound/sqlalchemy_repository.py` | Mapping + concurrency check |
| `app/infrastructure/orm_models.py` | SQLAlchemy mapping and explicit `version_id` |
| `examples/domain_events.py` | Aggregate-emitted domain event (no publishing or event sourcing) |
| `tests/test_domain.py` | Executable invariant tests |

### Limitations

- The old lab stores money as floats; a real financial system should use `Decimal` and explicit currency value objects.
- A true *application service* layer could further separate use cases from FastAPI request handlers.
- Domain events are generated and collected in memory but **not** connected to an event bus/outbox; the HTTP use case demonstrates only local state persistence. They are not an Event Sourcing log.
- The old `xmin` mapping has been replaced by an explicit integer version, with a simplified `expected_version` contract.

## Cleanup

```bash
make down
make reset  # WARNING: deletes Postgres volume
```

### Hexagonal layers

- `app/domain/models.py`: Aggregate Root, invariants, domain notifications (no Event Sourcing).
- `app/application/order_service.py`: create/read/change/delete use cases.
- `app/ports/`: repository and unit-of-work abstractions.
- `app/adapters/outbound/`: SQLAlchemy repository and UoW implementations.
- `app/adapters/inbound/`: FastAPI routes, schemas, serialization.
- `app/infrastructure/`: SQLAlchemy engine and ORM mapping used only by adapters/bootstrap.
