# Microservices Coordination and Orchestration — Examples

Hands-on examples for **Microservices Coordination and Orchestration**, Chapter 4 of the **Information Systems Design and Big Data** course (Polytechnic University of Bari).

The labs follow the progression of the slides: asynchronous request processing, transactional messaging, outbox relay strategies, distributed Sagas and DDD aggregates. Every lab has its own README and can be run **independently**; it is not one big distributed application. **The runnable services use a lightweight Hexagonal (Ports & Adapters) architecture**, building on the previous course block.

## Recommended lab sequence

| # | Directory | Main architectural concept |
|---|---|---|
| 0 | [`asynchronous-request-processing/`](asynchronous-request-processing/) | REST `202 Accepted`, validations continuing asynchronously via RabbitMQ; motivation for reliable publishing |
| 1 | [`transactional-outbox/polling-publisher/`](transactional-outbox/polling-publisher/) | Transactional Outbox with a **Polling Publisher** (PostgreSQL + Python SQL relay + RabbitMQ) |
| 2 | [`transactional-outbox/transaction-log-tailing/`](transactional-outbox/transaction-log-tailing/) | The **same Outbox Pattern**, using PostgreSQL **WAL** + **Python psycopg2/wal2json** + **RabbitMQ** (no Debezium or Kafka) |
| 3 | [`saga-choreography/`](saga-choreography/) | Distributed Saga, local transactions, compensation, decentralized event reactions; Adminer and per-service RabbitMQ DLQs |
| 4 | [`saga-orchestration/`](saga-orchestration/) | Explicit `SagaCoordinator` / `SagaStateMachine`, commands and replies, compensation, PostgreSQL state/history with Adminer, delayed retriable actions and idempotence |
| 5 | [`saga-isolation/`](saga-isolation/) | Lost updates, interleavings, semantic locks, reread/version techniques |
| 6 | [`ddd-aggregates/`](ddd-aggregates/) | Aggregate roots, invariants, repositories, domain events; **no Event Sourcing** |

## Key architectural distinctions

- **CAP and asynchronous processing:** CAP concerns consistency vs availability during a partition. Async messaging reduces temporal coupling, but does not eliminate failures or make a distributed operation atomic.
- **Outbox:** `orders` stores current business state. The outbox stores outgoing publication intentions in the same local database transaction; it is **not** an event-sourced history.
- **Two relay mechanisms:** *Polling Publisher* queries `PENDING` outbox rows and marks them sent after broker confirmation. *Transaction Log Tailing* uses a Python `psycopg2` replication client and PostgreSQL `wal2json` to read committed outbox inserts from the WAL and publish to RabbitMQ. Both can deliver duplicates and need idempotent consumers. Both provide **Adminer on port 8082** for inspecting the database and contrasting table-based status with WAL offset tracking.
- **CDC vs Event Sourcing:** Log tailing uses CDC internally, but is not Event Sourcing. CDC for general data replication and streaming is explored in Chapter 5.
- **Saga vs aggregate:** A Saga coordinates local transactions across services, whereas an aggregate enforces invariants inside one service/transaction boundary.
- **Orchestration lab:** Implements an explicit coordinator in Python, without a third-party workflow framework.

## Messaging reliability: what each lab demonstrates

- **Outbox (both relays):** atomic business-data and outbox writes, publisher confirms, and possible duplicate deliveries; the polling relay records `SENT`, while log tailing advances a PostgreSQL replication offset.
- **Saga Choreography:** durable queues, manual ACK, inbox deduplication and **per-service DLQs**. Rejected messages are quarantined, **not automatically retried**; AMQP reconnect backoff is a separate mechanism.
- **Saga Orchestration:** durable command/reply messaging, transition history, and **controlled post-pivot retries** through 2-second TTL queues. Those queues return commands for another attempt; they are **not final DLQs**. Unexpected handler errors are not covered by a full poison-message strategy in this teaching implementation.
- **Adminer:** inspect database state and technical tables in the PostgreSQL-backed examples; Saga Choreography and Saga Orchestration expose four isolated service databases.

See the individual README files for the exact commands, expected state changes and known limitations.

## Getting started

Clone the repository and choose **one** lab:

```bash
git clone https://github.com/saverioieva/information-systems-design-big-data-examples.git
cd information-systems-design-big-data-examples/microservices-coordination-and-orchestration
cd transactional-outbox/transaction-log-tailing
make up
make create
make outbox
make received
make wal
make down
```

For the polling alternative, use `cd transactional-outbox/polling-publisher` from this chapter directory and follow its README. Other examples have separate `Makefile` targets and may use different ports.

Most containerized examples require Docker Compose, `make`, and `curl`. Some labs have optional local Python unit tests. **Run one lab at a time:** several independently defined stacks use RabbitMQ management port `15672` or other shared host ports.

## What to observe

1. Locate the local database transaction boundary and identify who owns the business state.
2. Trace outgoing messages and determine what happens if the broker/consumer is unavailable.
3. Observe a successful flow, then experiment with a restart or simulated failure where supported.
4. Read the lab's limitations and compare the architectural alternatives before cleanup.

```bash
docker compose ps
docker compose logs
docker compose down        # preserve volumes
docker compose down -v     # WARNING: deletes local lab state
```

## Scope and verification

These are teaching exercises, **not production-ready templates**. They use local demonstration credentials and simplified recovery/observability. The accompanying code and configuration have static validation and selected unit tests; an actual Docker end-to-end run should be performed on the target machine before a classroom demonstration.

## Architecture: Domain, Application, Ports & Adapters

Each runnable service separates **pure domain rules**, **application use cases**, **ports** (repository and messaging interfaces), and **inbound/outbound adapters** (HTTP, RabbitMQ, SQLite/PostgreSQL). `main.py` or `app.py` is the composition root, not the place for domain rules. The code organization is intentionally compact to keep each lab readable.

- `asynchronous-request-processing/`: OrderUseCases, SQLite port/adapter, RabbitMQ publisher, Flask HTTP adapter.
- `transactional-outbox/polling-publisher/`: one atomic SQL adapter for order + outbox; polling relay uses an injected publisher port.
- `transactional-outbox/transaction-log-tailing/`: same business transaction; Python logical replication adapter reads WAL using `psycopg2` + `wal2json`, publishing with `pika` to RabbitMQ.
- `saga-choreography/`: each participant owns its database and has domain/application/ports/adapters.
- `saga-orchestration/`: `SagaStateMachine` (pure domain logic), `SagaCoordinator` (application layer), participant command handlers, four PostgreSQL containers (one per participant) with SQLAlchemy Core adapters, Adminer, and retry/idempotence demonstrations. Run `make retry` to observe a rollback and delayed re-execution of `ApproveTicket` and `ApproveOrder`.
- `ddd-aggregates/`: repository and unit-of-work ports isolate the aggregate from SQLAlchemy.
- `saga-isolation/`: pure in-memory scenarios, not a network service; no artificial infrastructure adapters.

The design is for teaching, not an assertion of production readiness. **The outbox is not Event Sourcing**, and the PostgreSQL logical replication slot tracks persistent WAL progress.
