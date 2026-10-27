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
POST /orders -> API -> [Postgres: orders + outbox]  (one transaction)
                                    |
                             polling relay
                                    |
                         publisher confirms
                                    v
                    RabbitMQ exchange outbox.events
                                    |
                              audit queue
                                    |
                 audit consumer -> received_events (dedup)
```

The example uses one Postgres database for the Order Service and a teaching-only audit consumer storing its deduplication marker in the same database. **In production, each service should own its database.** We use the shared database here only to isolate the outbox mechanism from service boundaries.

## Run

Requirements: Docker Compose, Make, and `curl`. Ports: `8000` (API), `15672` (RabbitMQ UI), `8082` (Adminer).

```bash
make up
make create
make outbox
make received
make logs
```

RabbitMQ UI: <http://localhost:15672> (`student` / `student`).

### Inspect the database with Adminer

Adminer is included in this lab's `docker-compose.yml`. Open
<http://localhost:8082> and log in with:

| Field | Value |
|---|---|
| System | PostgreSQL |
| Server | `postgres` |
| Username | `demo` |
| Password | `demo` |
| Database | `orders` |

In **SQL command**, run:

```sql
SELECT id, amount, status FROM orders;
SELECT event_id, routing_key, status, attempts, created_at, sent_at
FROM outbox ORDER BY created_at DESC;
SELECT event_id, aggregate_id, received_at
FROM received_events ORDER BY received_at DESC;
```

Create an order with `make create`. The relay may move the outbox row from
`PENDING` to `SENT` quickly; use `make broker-pause` before creating an order
if you want to observe `PENDING` reliably, then `make broker-resume` to see `SENT`.
Adminer is a **database viewer**, not the message broker management UI.


### Source reading order

| File / function | Concept |
|---|---|
| `app/adapters/outbound/postgres_repository.py` — `save_order_and_message()` | Business update and outbox insert in **one** DB transaction |
| `app/application/use_cases.py` — `PollingRelay.publish_once()` | Polling, publisher confirmation, marking `SENT` |
| `app/adapters/inbound/audit_consumer.py` — `run()` | `basic_ack` after persistence, deduplication by event ID |
| `docker-compose.yml` | Separate API, relay and consumer processes |

### Exercise 1 — Observe a successful event

1. Run `make up`; then `make create`.
2. Observe the JSON API response: it contains `eventId` and `orderId`.
3. Run `make outbox`: the row should eventually show `status: SENT`.
4. Run `make received`: there should be one row with the matching `eventId`.
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

`relay()` has a teaching switch `CRASH_AFTER_CONFIRM=1`. Set it in the `relay` service environment and recreate the relay, then create an order. The relay exits **after** a broker confirmation but **before** the database update to `SENT`. Restarting it without the switch republishes the event; `received_events` is protected by a unique event ID.

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
make reset    # WARNING: delete persisted data
```

## Hexagonal code map

| Layer | Code |
|---|---|
| Domain | `app/domain/order.py`: current-state order notification |
| Application | `app/application/use_cases.py`: order creation, polling relay, audit handler |
| Ports | `app/ports/repositories.py`, `app/ports/publisher.py` |
| Outbound adapters | `app/adapters/outbound/`: SQLAlchemy repository and RabbitMQ publisher |
| Inbound adapters | `app/main.py`: FastAPI composition root; `app/adapters/inbound/audit_consumer.py` |

The outbox write remains in the PostgreSQL adapter inside one transaction; the application only asks the repository to persist the order **and** publication intention atomically.
