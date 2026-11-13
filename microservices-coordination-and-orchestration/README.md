# Microservices Coordination and Orchestration — Examples

Hands-on examples for **Microservices Coordination and Orchestration**, Chapter 4 of the **Information Systems Design and Big Data** course (Polytechnic University of Bari).

The labs follow the progression of the slides: asynchronous request processing, transactional messaging, Outbox relay strategies, distributed Sagas, isolation between concurrent Sagas, and DDD Aggregates with Domain Events. Every lab has its own README and can be run **independently**; this is not one large distributed application. Runnable services use a lightweight **Hexagonal (Ports & Adapters) architecture**, building on the previous course block.

## Recommended lab sequence

| # | Directory | Main architectural concept |
|---|---|---|
| 0 | [`asynchronous-request-processing/`](asynchronous-request-processing/) | REST `202 Accepted`, validation continuing asynchronously via RabbitMQ; motivation for reliable publishing |
| 1 | [`transactional-outbox/polling-publisher/`](transactional-outbox/polling-publisher/) | Transactional Outbox with a **Polling Publisher** (PostgreSQL + Python SQL relay + RabbitMQ) |
| 2 | [`transactional-outbox/transaction-log-tailing/`](transactional-outbox/transaction-log-tailing/) | The **same Outbox Pattern**, using PostgreSQL **WAL** + **Python `psycopg2`/`wal2json`** + **RabbitMQ** (no Debezium or Kafka) |
| 3 | [`saga-choreography/`](saga-choreography/) | Distributed Saga, local transactions, compensations and decentralized event reactions; per-service PostgreSQL, bounded-context topic exchanges and DLQs |
| 4 | [`saga-orchestration/`](saga-orchestration/) | Explicit `SagaCoordinator` / `SagaStateMachine`, commands and replies, compensations, PostgreSQL state/history, delayed retries and idempotence |
| 5 | [`saga-isolation/`](saga-isolation/) | **Two competing Sagas (`CreateOrder` and `CancelOrder`)** using RabbitMQ and four real PostgreSQL instances; deterministic unsafe interleaving, semantic lock and optimistic locking |
| 6 | [`ddd-aggregates/`](ddd-aggregates/) | `Order` Aggregate Root, invariants, repository/Unit of Work, optimistic locking, Domain Events, and atomic persistence of the Order plus an Integration Event intent; **no Event Sourcing** |

## Key architectural distinctions

- **CAP and asynchronous processing:** CAP concerns consistency versus availability during a network partition. Async messaging reduces temporal coupling but does not eliminate failures or make a distributed business operation atomic.
- **Outbox:** `orders` holds current business state. The Outbox stores outgoing publication intentions in the **same local database transaction**; it is **not** an event-sourced history.
- **Two relay mechanisms:** *Polling Publisher* queries `PENDING` Outbox rows and marks them sent after broker confirmation. *Transaction Log Tailing* uses a Python `psycopg2` replication client and PostgreSQL `wal2json` to read committed Outbox inserts from the WAL and publish to RabbitMQ. Both can deliver duplicates and require idempotent consumers. Both expose **Adminer on port 8082** to inspect the databases and compare table-based status with WAL offset tracking.
- **CDC versus Event Sourcing:** Log tailing uses Change Data Capture internally, but it is not Event Sourcing. General-purpose CDC, Debezium and Kafka are explored in Chapter 5.
- **Local ACID versus Saga isolation:** Each service can commit a correct ACID transaction while the overall business workflow remains vulnerable to interference from another Saga. Semantic locks, guarded state transitions and optimistic version checks address this at the application level; increasing SQL isolation alone does not make a Saga globally isolated.
- **DDD Aggregate versus Saga:** An Aggregate Root enforces local invariants and changes its own state in one ACID transaction. A Saga coordinates steps across independent service-owned transactions.
- **Domain Event versus Integration Event:** `OrderCreated` / `OrderApproved` describe facts raised by the Order model; the application layer may select a transport-facing Integration Event. The DDD lab persists a publication intent but does **not** run its own relay.
- **Orchestration lab:** Implements an explicit coordinator in Python without a third-party workflow framework.
- **Isolation lab:** Extends the same architecture with a *separate* `CancelOrder` workflow. The intentionally incorrect `unsafe` mode is enabled only for the demonstration; it is not the default approval policy.

## Messaging reliability: what each lab demonstrates

- **Outbox (both relays):** Atomic business-data and Outbox writes, publisher confirms, and possible duplicate deliveries; the polling relay records `SENT`, whereas log tailing advances a PostgreSQL replication offset.
- **Saga Choreography:** Durable queues, manual ACK, Inbox deduplication, **four topic exchanges (one per bounded context)** and **per-service DLQs**. Rejected messages are quarantined, **not automatically retried**; AMQP reconnect backoff is a separate mechanism.
- **Saga Orchestration:** Durable command/reply messaging, transition history, and **controlled post-pivot retries** through 2-second TTL queues. These queues return commands for another attempt; they are **not terminal DLQs**. Unexpected handler errors are not covered by a complete poison-message recovery strategy.
- **Saga Isolation:** Uses the same durable commands/replies, local Outbox/Inbox and idempotent participants as Orchestration. An `ApproveOrder` message is **held in the persisted Outbox** until the demo explicitly releases it; the other messages continue flowing. This provides a repeatable interleaving without keeping PostgreSQL transactions open. `CancelOrder` invokes `VoidAuthorization` in Accounting and `RejectTicket` in Kitchen before the Order Service records `CANCELLED`.
- **DDD Aggregates:** Shows immutable Domain Events raised by the domain, the current-state `orders` and `order_line_items` tables, and an `integration_outbox` committed atomically with a state change. No event store, Kafka consumer or broker publisher is implemented in this lab.
- **Adminer:** Inspect local business state and technical tables in the PostgreSQL-backed examples. Choreography, Orchestration and Isolation use **four service-owned PostgreSQL instances**, not a shared application database.

See each lab's README for exact commands, expected state changes, transaction boundaries and known limitations.

## Getting started

Clone the repository and select **one** lab:

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

For the polling alternative, return to the chapter directory and enter `transactional-outbox/polling-publisher/`; follow its README for the available Makefile commands. Other labs use their own Compose stacks and may expose overlapping host ports.

### Saga Isolation: competing workflows

From the chapter directory:

```bash
cd saga-isolation
make up
make status
make unsafe      # CANCELLED is incorrectly overwritten by APPROVED
make semantic    # Concurrent cancellation is refused (409); retry after approval
make optimistic  # Version/state guard prevents the stale approval
make logs
make down
```

Each scenario creates a **fresh order** and waits for an explicit, persistent pause before releasing the held approval. The demo does not depend on random timing or `sleep()`-based race conditions. Inspect the order and compensation states in Adminer at `http://localhost:8082` (for example, `postgres_order` / `order_db`, user `demo`, password `demo`). See [`saga-isolation/README.md`](saga-isolation/README.md) for the full workflow and SQL inspection queries.

### DDD Aggregates and Domain Events: after the DDD slides

From the chapter directory:

```bash
cd ddd-aggregates
make up
make create      # returns an order ID, with OrderCreated recorded locally
make events      # show integration_outbox publication intents
make db          # inspect outbox entries in PostgreSQL
make approve ORDER_ID=<id> VERSION=1
make events      # now also shows OrderApproved
make down
```

Use this lab after **"Generating and Publishing Domain Events"** in the Chapter 4 slides. Inspect the API at `http://localhost:8003/docs` and the database in Adminer at `http://localhost:8083`. The Aggregate validates business rules; the application service saves the current Order and the selected Outbox event intent in one local transaction. This lab **does not implement Event Sourcing** or publish to Kafka/RabbitMQ; the Chapter 4 Outbox labs already explain the actual relay.

Most containerized examples require Docker Compose, `make`, and `curl`; the Isolation demo additionally uses **Python 3 (standard library)** on the host. Some labs provide optional local Python tests. **Run one lab at a time:** independent stacks may reuse RabbitMQ management ports, Adminer port `8082`, or the Order API port `8001`.

## What to observe

1. Identify each service's local transaction boundary and the database that owns its business data.
2. Trace outgoing messages and ask what happens if the broker, relay, or consumer is temporarily unavailable.
3. Observe the successful flow, then use the supported failure, retry, compensation or DLQ scenarios.
4. In **Saga Isolation**, compare the same two business workflows under `unsafe`, `semantic` and `optimistic`: **local ACID still holds**, but the final cross-service outcome changes.
5. In **DDD Aggregates**, compare `Order.create()` / `Order.approve()`, the resulting Domain Events, and the current-state SQL rows; verify that invalid transitions and stale versions are rejected.
6. Read the limitations and compare architectural alternatives before cleaning up.

```bash
docker compose ps
docker compose logs
docker compose down       # preserve volumes
docker compose down -v    # WARNING: deletes local lab data
```

## Scope and verification

These are teaching exercises, **not production-ready templates**. They use local demonstration credentials and simplified recovery/observability. The code and configuration have static validation and selected unit tests; perform a Docker end-to-end run on the target machine before a classroom demonstration.

In particular, the Isolation lab's `unsafe` path **deliberately bypasses the normal state guard**. The incorrect final state demonstrates a business-level concurrency anomaly between separately committed Saga steps, **not a failure of PostgreSQL's ACID guarantees**. Its compensation flow models voiding a card authorization, not refunding a settled payment.

## Architecture: Domain, Application, Ports & Adapters

Each runnable service separates **domain rules**, **application use cases**, **ports** (persistence and messaging interfaces), and **inbound/outbound adapters** (HTTP, RabbitMQ, SQLite/PostgreSQL). `main.py` or `app.py` acts as the composition root rather than a place for domain rules. The organization remains intentionally compact for teaching.

- `asynchronous-request-processing/`: `OrderUseCases`, SQLite port/adapter, RabbitMQ publisher, Flask HTTP adapter.
- `transactional-outbox/polling-publisher/`: One atomic SQL adapter for Order + Outbox; the polling relay uses an injected publisher port.
- `transactional-outbox/transaction-log-tailing/`: Same local business transaction; a Python logical replication adapter reads WAL with `psycopg2` + `wal2json` and publishes via `pika` to RabbitMQ.
- `saga-choreography/`: Each participant owns its PostgreSQL instance and implements local domain/application/ports/adapters; events route through bounded-context topic exchanges.
- `saga-orchestration/`: `SagaStateMachine` (pure domain logic), `SagaCoordinator` (application layer), participant command handlers, **four PostgreSQL containers**, Adminer, Outbox/Inbox and retry/idempotence demonstrations. `make retry` shows a rolled-back local attempt followed by delayed retry of `ApproveTicket` and `ApproveOrder`.
- `saga-isolation/`: A **standalone distributed project**, not the former in-memory simulation. It retains Orchestration's four services, four PostgreSQL instances and RabbitMQ, and adds `CancelOrderStateMachine`, persisted cancellation history, compensating commands, a durable Outbox approval gate and conditional SQL updates. The `demo/run_scenario.py` driver reproduces the three isolation scenarios deterministically.

- `ddd-aggregates/`: `Order` Aggregate Root and immutable Domain Events in the domain layer, application service plus Repository/Unit of Work ports, FastAPI and SQLAlchemy adapters, PostgreSQL current-state and `integration_outbox` tables. No broker is required.

The design is for teaching, not a claim of production readiness. **The Outbox is not Event Sourcing**, and a PostgreSQL logical replication slot tracks persistent WAL consumption progress.

