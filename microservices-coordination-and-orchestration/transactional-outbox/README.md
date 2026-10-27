# Transactional Outbox — Two Relay Strategies

Both labs implement the **same Transactional Outbox Pattern**, using a PostgreSQL
`orders` table for **current application state**, a separate `outbox` table for
**pending outbound messages**, and RabbitMQ for delivery. **Neither lab uses
Event Sourcing.** Each lab is independently runnable with Docker Compose.

| Lab | Where messages come from | Relay | Broker |
|---|---|---|---|
| [Polling Publisher](polling-publisher/) | Repeated SQL queries over pending outbox rows | Python + SQLAlchemy | RabbitMQ |
| [Transaction Log Tailing](transaction-log-tailing/) | Committed outbox inserts decoded from PostgreSQL WAL | Python + `psycopg2` + `wal2json` | RabbitMQ |

## Start one lab

```bash
cd polling-publisher
make up
make create
make outbox
make received
make down

# From polling-publisher/, move to the sibling lab:
cd ../transaction-log-tailing
make up
make create
make wal
make received
make down
```

**Run only one at a time:** both map RabbitMQ management to host port 15672.
Both services demonstrate **Domain → Application → Ports → Adapters**, with
RabbitMQ and PostgreSQL behind interfaces. The consumer is idempotent.

## Inspect the databases with Adminer

Both labs include **Adminer** at <http://localhost:8082>. Use **PostgreSQL**,
server `postgres`, database `orders`, username `demo`, password `demo`.

- **Polling Publisher:** inspect `outbox.status` (`PENDING` then `SENT`).
- **Transaction Log Tailing:** inspect append-only `outbox_events` and query
  `pg_replication_slots` for the WAL position (`confirmed_flush_lsn`).

Use only one lab at a time; the Adminer and RabbitMQ UI host ports overlap.
Each lab README provides ready-to-run SQL queries.

## Key comparison

The polling relay publishes an outbox row, waits for broker confirmation and
updates its status to `SENT`. If it crashes before the status update, the event
may be delivered again.

The log-tailing relay publishes an outbox INSERT seen in the WAL, waits for broker
confirmation and then **acknowledges the WAL position** via a PostgreSQL logical
replication slot. A crash before the position is recorded can also cause duplicates.

**The database transaction guarantees only the atomic write of business state +
outbox row. It does not create a distributed transaction with RabbitMQ.**

In Chapter 5, Change Data Capture can be explored as a more general technique,
for example using Debezium and Kafka, without implementing an Outbox Pattern.
