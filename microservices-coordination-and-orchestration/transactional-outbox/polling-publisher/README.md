# Transactional Outbox — PostgreSQL + RabbitMQ + Python

This lab follows the **Transactional Messaging**, **Outbox**, **Polling Publisher**, and **Transaction Log Tailing** slides.

**Chapter 4 / Transactional Outbox / relay strategy A: Polling Publisher.** This exercise implements the transactional outbox using PostgreSQL and RabbitMQ.

The slides also introduce **Transaction Log Tailing**. The sibling [Transaction Log Tailing lab](../transaction-log-tailing/) implements this with **PostgreSQL WAL + Python (`psycopg2` / `wal2json`) + RabbitMQ**, so students can compare the relay methods without changing the broker.

## Learning objectives

- See why `UPDATE database; PUBLISH event` is **not atomic** when performed as two independent operations.
- Store an `OrderCreated` event in the **same PostgreSQL transaction** as its Order.
- Watch a background **polling relay** send an outbox event to RabbitMQ, wait for **publisher confirmation**, and mark it `SENT`.
- Understand **at-least-once** delivery and **idempotent consumers**.
- Compare the SQL-based relay against the separate **Python WAL-based log-tailing** exercise.

## Architecture

```text
POST /orders -> Order API -> [postgres_order: orders + outbox] (one transaction)
                                          |
                                   polling relay
                                          |
                                   RabbitMQ publish
                                   + broker confirm
                                          v
                                   outbox.audit queue
                                          |
                                   Audit Consumer
                                          |
                          [postgres_audit: received_events]
```

**Database per Service:** Order API and the polling relay use `postgres_order` (`orders` database) because the relay must read the Order Service's outbox. The Audit Consumer uses **its own PostgreSQL container**, `postgres_audit` (`audit` database), and writes only `received_events` there. Each PostgreSQL instance has a separate persistent Docker volume. Services exchange events through RabbitMQ; the Order API never reads the Audit database.

## Run

Requirements: Docker Compose, Make, and `curl`. Ports: `8000` (API), `15672` (RabbitMQ UI), `8082` (Adminer).

```bash
make up
make status    # Inspect Docker Compose containers
make create
make outbox     # Order database: PENDING/SENT
make received   # Audit database: deduplicated deliveries (psql)
make logs
```

RabbitMQ UI: <http://localhost:15672> (`student` / `student`).

### Inspect the database with Adminer

Adminer is included in this lab's `docker-compose.yml`. Open
<http://localhost:8082> and log in with:

| Field | Value |
|---|---|
| System | PostgreSQL |
| Server | `postgres_order` |
| Username | `demo` |
| Password | `demo` |
| Database | `orders` |

**Order database** — connect to server `postgres_order`, database `orders`:

```sql
SELECT id, amount, status FROM orders;
SELECT event_id, routing_key, status, attempts, created_at, sent_at
FROM outbox ORDER BY created_at DESC;
```

**Audit database** — log out of Adminer and reconnect using server `postgres_audit`, database `audit` (same demo credentials):

```sql
SELECT event_id, aggregate_id, received_at
FROM received_events ORDER BY received_at DESC;
```

`received_events` is deliberately **not** in the Order database. `make received`
queries `postgres_audit` using `psql`, not an Order API endpoint (`GET /received`
has been removed to avoid cross-service database access).

Create an order with `make create`. The relay may move the outbox row from
`PENDING` to `SENT` quickly; use `make broker-pause` before creating an order
if you want to observe `PENDING` reliably, then `make broker-resume` to see `SENT`.
Adminer is a **database viewer**, not the message broker management UI.


### Source reading order

| File / function | Concept |
|---|---|
| `app/adapters/outbound/postgres_repository.py` — `save_order_and_message()` | Business update and outbox insert in **one** DB transaction |
| `app/application/use_cases.py` — `PollingRelay.publish_once()` | Polling, publisher confirmation, marking `SENT` |
| `app/adapters/inbound/audit_consumer.py` — `run()` | `basic_ack` after persisting in the **Audit** database; deduplication by event ID |
| `app/adapters/outbound/postgres_audit_repository.py` | Audit-only adapter: `received_events` unique `event_id` |
| `docker-compose.yml` | Two PostgreSQL containers / volumes; independent Order and Audit ownership |

### Exercise 1 — Observe a successful event

1. Run `make up`; then `make create`.
2. Observe the JSON API response: it contains `eventId` and `orderId`.
3. Run `make outbox`: the row should eventually show `status: SENT`.
4. Run `make received`: the **Audit database** should contain one row with the matching `eventId`.
5. Locate the `outbox.events` topic exchange and `outbox.audit` queue in RabbitMQ UI.

### Exercise 2 — Broker temporarily unavailable

```bash
make broker-pause
make create
make outbox
make broker-resume
make outbox
make received
```

While the broker is stopped the **API still commits the order and outbox entry**. After restarting RabbitMQ, the relay publishes the pending event. Allow a few seconds for retries.

### Exercise 3 — Why duplicates are possible

`relay()` has a teaching switch `CRASH_AFTER_CONFIRM=1`. Set it in the `relay` service environment and recreate the relay, then create an order. The relay exits **after** a broker confirmation but **before** the database update to `SENT`. Restarting it without the switch republishes the event; the **Audit database's** `received_events` table is protected by a unique event ID.

The example demonstrates **at-least-once**, *not exactly-once*. Publisher confirms establish broker acceptance but cannot atomically commit PostgreSQL and RabbitMQ together.

### Exercise 4 — Compare with Transaction Log Tailing (runnable sibling lab)

The slides introduce **Transaction Log Tailing** as a second way for a relay to discover committed outbox messages. Instead of repeatedly querying outbox rows, a log-tailing component reads the database transaction log.

| Polling Publisher (this directory) | Transaction Log Tailing ([open lab](../transaction-log-tailing/)) |
|---|---|
| Reads pending rows with SQL queries | Reads committed changes from the database transaction log |
| Python relay publishes to RabbitMQ | A log-reading connector/relay forwards committed outbox records |
| Polling interval affects latency | Log-stream processing can reduce idle polling |
| Relay marks entries `SENT` after confirm | Progress tracking depends on the chosen log reader |
| Must handle retry and duplicates | Also requires recovery and duplicate handling |

**Next exercise:** go to `../transaction-log-tailing/`, run `make up`, and compare the same RabbitMQ message flow with a Python `psycopg2` WAL reader instead of a Python polling relay. Stop the polling stack first with `make down` because both use ports `15672` (RabbitMQ UI) and `8082` (Adminer). **Chapter 5** introduces CDC as a more general data-integration technique, separately from the outbox.

**Scope limitations (polling implementation):** one relay instance; no claim/lease for multiple relays, no dead-letter handling or full crash recovery test harness. These are topics for a production design, not guarantees provided by this demo.

## Cleanup

```bash
make down     # keep database volumes
make reset    # WARNING: delete BOTH PostgreSQL volumes and RabbitMQ data
```

## Hexagonal code map

| Layer | Code |
|---|---|
| Domain | `app/domain/order.py`: current-state order notification |
| Application | `app/application/use_cases.py`: order creation, polling relay, audit handler |
| Ports | `app/ports/repositories.py`, `app/ports/audit_repository.py`, `app/ports/publisher.py` |
| Outbound adapters | `app/adapters/outbound/`: separate Order/Audit SQLAlchemy repositories and RabbitMQ publisher |
| Inbound adapters | `app/main.py`: FastAPI composition root; `app/adapters/inbound/audit_consumer.py` |

The outbox write remains in the Order PostgreSQL adapter inside one transaction; the application only asks the repository to persist the order **and** publication intention atomically. The Audit Consumer persists its own deduplication record and acknowledges RabbitMQ **after** that transaction commits.

**Upgrading from an earlier shared-database version:** use `make down`, then `make reset` (destructive), then `make up` for a clean lab. New named volumes are independent; the old shared database volume is not migrated. A previous `received_events` table in an old Order volume is historical data, not used by this version.
