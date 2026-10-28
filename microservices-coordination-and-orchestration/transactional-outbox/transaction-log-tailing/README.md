# Transaction Log Tailing — Python + PostgreSQL WAL + RabbitMQ

**Chapter 4 / Transactional Outbox / relay strategy B**

This lab implements the **same Transactional Outbox Pattern** as the sibling
[`polling-publisher/`](../polling-publisher/), but replaces its SQL polling relay
with an explicitly implemented **Python WAL tailing relay**. There is **no Debezium,
Kafka, or Event Sourcing** in this lab.

## Learning objectives

- Commit the order's **current state** and an outbox publication intention **in one transaction**.
- Read committed outbox INSERTs directly from the PostgreSQL WAL with
  `psycopg2.extras.LogicalReplicationConnection` and the `wal2json` output plugin.
- Relay messages using `pika` and RabbitMQ **publisher confirmations**.
- Observe a PostgreSQL logical replication slot and its persisted confirmed WAL position.
- Understand why duplicates are still possible: **at-least-once** delivery and idempotent consumers.

## Architecture

```text
   Client --POST /orders--> FastAPI Order Service
                                 |
                        postgres_order (orders DB)
                   INSERT orders + outbox_events
                         (one transaction)
                                 |
                      PostgreSQL WAL (logical)
                                 |
              Python relay [psycopg2 + wal2json]
                     [Pika publisher confirms]
                                 |
                      RabbitMQ outbox.events
                                 |
                         Audit Consumer
                                 |
                       postgres_audit (audit DB)
                      received_events (dedup)
```

**Not Event Sourcing:** `orders` is the authoritative current state; `outbox_events`
is an append-only table of messages to publish, not the source for reconstructing state.
The Audit Consumer **owns a separate PostgreSQL instance**, `postgres_audit`,
with its own `audit` database and volume. Its `received_events` table never
lives in the Order Service database. The WAL relay connects **only** to
`postgres_order`, where the Order Service owns the outbox and the replication slot.

## Requirements and running

Docker Compose, `make`, `curl`. Start this lab **separately** from the polling lab
because host ports `15672` (RabbitMQ UI) and `8082` (Adminer) are shared. Host API port: `8004`.

```bash
make up
make status
make create
make orders
make outbox
make received   # Query postgres_audit with psql
make wal        # Inspect the slot on postgres_order
```

UI: http://localhost:15672 (`student` / `student`). The exchange is `outbox.events`
(topic), routing key `order.created`, queue `outbox.audit`.

### Inspect the database with Adminer

Adminer runs as a service in this lab. Open <http://localhost:8082>:

| Field | Value |
|---|---|
| System | PostgreSQL |
| Server | `postgres_order` |
| Username | `demo` |
| Password | `demo` |
| Database | `orders` |

In **SQL command** on **`postgres_order`**, inspect Order state and outbox:

```sql
SELECT id, amount, status FROM orders;
SELECT event_id, aggregate_id, event_type, created_at
FROM outbox_events ORDER BY created_at DESC;
```

Reconnect to Adminer with **server `postgres_audit`, database `audit`**
(same `demo` / `demo` credentials) to inspect the consumer's own data:

```sql
SELECT event_id, order_id, received_at
FROM received_events ORDER BY received_at DESC;
```

`make received` executes this query in the **Audit** PostgreSQL container.
The Order API no longer exposes `GET /received`, because it cannot read another
service's database. There are **two separate PostgreSQL servers and volumes**.

Unlike the Polling Publisher example, `outbox_events` has **no `SENT` status**:
the relay tracks progress via the PostgreSQL logical replication slot. To inspect
its status from Adminer (or use `make wal`), run:

```sql
SELECT slot_name, plugin, active, confirmed_flush_lsn, restart_lsn
FROM pg_replication_slots;
```

Adminer shows the SQL-level replication metadata, **not the raw WAL records**.
Use `make wal` and `make logs` to follow transaction-log processing.


The `postgres_order` container runs with `wal_level=logical` and a `wal2json`
plugin; a dedicated `slot-init` container creates `outbox_slot` **on
`postgres_order`** before the HTTP API starts accepting requests, avoiding
missed early writes. The relay's changes
are restricted to `public.outbox_events` by `wal2json`'s `add-tables` setting.
The durable slot's `confirmed_flush_lsn` is stored by PostgreSQL, not in a
stateless Python process.

## Recommended reading order

| File | Responsibility |
|---|---|
| `app/domain/order.py` | Order state and outgoing notification intent |
| `app/application/use_cases.py` | Create order without publishing directly |
| `app/ports/repository.py` | Persistence interface |
| `app/adapters/outbound/postgres_repository.py` | Order DB: atomic SQL transaction inserting order and outbox row |
| `app/adapters/outbound/postgres_audit_repository.py` | Audit DB: idempotent `received_events` insert |
| `app/application/log_tail_relay.py` | Pure filtering of committed WAL batches |
| `app/ports/publisher.py` | Outbound messaging port |
| `app/adapters/inbound/postgres_wal_reader.py` | Logical replication slot, streaming and WAL acknowledgments |
| `app/adapters/outbound/rabbitmq_publisher.py` | RabbitMQ persistent publish + publisher confirms |
| `app/adapters/inbound/rabbitmq_consumer.py` | Consumer deduplication in Audit DB and acknowledgments |
| `db/Dockerfile` | **Order** PostgreSQL 16 with `wal2json` installed |
| `db/001_schema.sql` / `db/002_audit_schema.sql` | Order/outbox tables versus Audit-only delivery table |

## Experiments

**1 — Compare with polling.** Stop both labs before switching; run the polling
sibling and inspect its `PENDING -> SENT` status update. Here the outbox is
append-only, and **the durable WAL offset**, not the row status, records progress.

**2 — Observe recovery.** After `make up`, run `make relay-stop`, then
`make create`. The API still commits both rows. Run `make received` (no new row yet),
then `make relay-start`, and repeat `make received` and `make wal`.
`make received` reads the independent Audit database.

**3 — Observe broker outage.** Run `make broker-pause` and `make create`,
then `make broker-resume`. The relay retries and processes the retained WAL data.
A successful publisher confirmation must precede WAL feedback.

**4 — Discuss the failure window.** A relay can crash **after RabbitMQ confirms**
and **before PostgreSQL records WAL progress**; the message may be published
again after restart. The audit consumer's `event_id` is unique in its **own database** and uses
`ON CONFLICT DO NOTHING`. This is *at-least-once*, not exactly-once.

```bash
make logs
make relay-restart
make down      # preserve database, slot, broker state
make reset     # WARNING: delete both PostgreSQL volumes and broker data
```

## Important constraints

- This is a **teaching-only implementation**, not a production CDC engine.
  The Python relay doesn't implement production-grade monitoring, bounded WAL retention,
  schema evolution, snapshotting or HA failover.
- A replication slot can retain WAL when the relay is stopped or failing;
  check `make wal` and use `make reset` when finished.
- `wal2json` is a PostgreSQL logical decoding **plugin installed in the DB image**;
  `psycopg2` is the Python **replication client**. Python alone cannot decode the
  raw WAL without the server's decoding support.
- The relay uses RabbitMQ confirms and sends replication feedback only afterward;
  it can still replay messages on restart. The consumer must be idempotent.
- This lab starts from fresh databases and creates the replication slot before
  application writes. It intentionally has no existing-data snapshot or backfill.
- When replacing the old shared-database example, use `make down`, `make reset`
  (destructive), then `make up` to start fresh. The older shared DB volume is
  not migrated. The Order database should contain `orders` and `outbox_events`;
  the Audit database should contain only `received_events`.
- The delivery record is an **Audit-side idempotency marker**, not a shared
  Order/Audit table or distributed SQL transaction.

## Technical references

- [psycopg2 logical replication API](https://www.psycopg.org/docs/extras.html#replication-support-objects)
- [wal2json PostgreSQL output plugin](https://github.com/eulerto/wal2json)
- [PostgreSQL logical decoding](https://www.postgresql.org/docs/current/logicaldecoding.html)
