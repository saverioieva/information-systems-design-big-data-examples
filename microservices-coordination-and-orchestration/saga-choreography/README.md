# Create Order Saga - Choreography

A runnable lab for **Microservices Coordination and Orchestration**. The example adapts the previous-year `microservices/saga/choreography_pubsub_sqlalchemy/` project and uses a lightweight **hexagonal architecture** with FastAPI, PostgreSQL, SQLAlchemy, RabbitMQ and a polling transactional outbox.

This README contains the implementation material that can be removed from the lecture slides. The description below refers to the code in this repository, not to a hypothetical production implementation.

## Learning objectives

- Implement **saga choreography**: services react to domain events rather than commands from a central orchestrator.
- Keep separate PostgreSQL databases and local transactions per service.
- Combine local business changes and outbox inserts in a **single database transaction**.
- Use RabbitMQ topic routing, persistent messages, publisher confirms and manual consumer acknowledgments.
- Observe the Accounting decision (a simplified pivot) and the order/ticket state changes on success or failure.
- Inspect the per-service **dead-letter queues**, end-to-end `[flow]` logs, and Adminer; discuss duplicate delivery and the remaining production limitations.

## 1. Service-level implementation

| Service | Entry points and responsibility | Code |
|---|---|---|
| **Order Service** | FastAPI `POST /orders`, `GET /orders/{order_id}` and `GET /orders`; creates `APPROVAL_PENDING` orders plus `order.created` in its outbox; consumes final accounting results. | `order_service/app.py`, `order_service/application/use_cases.py`, `order_service/adapters/outbound/postgres_repository.py` |
| **Consumer Service** | Consumes `order.created`; looks up `consumers.can_order`; creates `consumer.verified` or `consumer.verificationFailed` in its outbox. | `consumer_service/app.py`, `consumer_service/adapters/outbound/postgres_repository.py` |
| **Kitchen Service** | Consumes `order.created` and creates a `CREATE_PENDING` ticket; subsequently handles accounting results, setting `TICKET_ACCEPTED` or `REJECTED`. | `kitchen_service/app.py`, `kitchen_service/adapters/outbound/postgres_repository.py` |
| **Accounting Service** | Listens for order, customer, and kitchen events; tracks prerequisites and determines whether to authorize or reject. The demo authorizes amounts **up to 100** when prerequisites pass. A failed customer validation rejects immediately. | `accounting_service/app.py`, `accounting_service/adapters/outbound/postgres_repository.py` |

The services use `domain/` for pure policies, `application/` for use cases and routing, `ports/` for repository contracts, and `adapters/outbound/` for SQLAlchemy persistence. Each `app.py` is the inbound HTTP/RabbitMQ adapter and composition root.

### RabbitMQ routing

`topology.py` creates the durable **topic exchange `saga`**, a durable **dead-letter exchange `saga.dlx`** (direct), and durable queues `order.q`, `consumer.q`, `kitchen.q`, `accounting.q`, and `audit.q`. Each main queue has a matching `<queue>.dlq`, e.g. `accounting.q.dlq`.

| Queue | Routing keys |
|---|---|
| `consumer.q` | `order.created` |
| `kitchen.q` | `order.created`, `accounting.creditCardAuthorized`, `accounting.creditCardAuthorizationFailed` |
| `accounting.q` | `order.created`, `consumer.verified`, `consumer.verificationFailed`, `kitchen.ticketCreated` |
| `order.q` | `accounting.creditCardAuthorized`, `accounting.creditCardAuthorizationFailed` |
| `audit.q` | `order.approved`, `order.rejected`, `kitchen.ticketRejected` |

An audit queue is declared but this lab does **not** run a separate audit consumer. Consumer handler failures use `basic_nack(requeue=False)`, which routes the rejected message to that service's DLQ. These queues intentionally have no automatic retry loop: inspect the failure before manual replay.

## 2. Per-service databases and SQLAlchemy

Each service owns its PostgreSQL database. No service directly queries another service's tables.

| Database | Local business tables | Shared technical tables |
|---|---|---|
| `orderdb` | `orders(order_id, customer_id, amount, status, created_at)` | `outbox`, `inbox` |
| `consumerdb` | `consumers(customer_id, can_order)` | `outbox`, `inbox` |
| `kitchendb` | `tickets(order_id, status, created_at)` | `outbox`, `inbox` |
| `accountingdb` | `prereq(order_id, have_order, have_consumer, have_ticket)`, `credit_auth(order_id, amount, status, updated_at)` | `outbox`, `inbox` |

The SQLAlchemy `Session` commits business changes, inbox deduplication markers and any outgoing outbox rows in one **local** database transaction. The code uses PostgreSQL-specific `ON CONFLICT` upserts and JSONB, so **database portability is not demonstrated** simply by using SQLAlchemy.

See `libs/saga_common/saga_common/__init__.py` for shared `outbox` and `inbox` definitions and `claim_message(...)`; the service repository adapters contain their local SQL transactions.

## 3. Transactional outbox and publisher threads

When the Order Service creates an order, one PostgreSQL commit records:

1. The order in `orders` with `APPROVAL_PENDING`.
2. The pending message in `outbox` with routing key `order.created`.

The other services use the same principle for their own outgoing events. Each service starts a **background polling publisher thread** (`publish_outbox_forever` in `libs/saga_common/saga_common/__init__.py`), separate from its HTTP handler or RabbitMQ consumer loop.

The publisher selects `PENDING` rows, publishes them via **Pika `BlockingConnection`**, waits for RabbitMQ **publisher confirms**, then updates the row to `SENT`. It calls `conn.sleep(0.3)` when idle so the blocking connection can process connection events/heartbeats. The publisher and consumer AMQP reconnection loops use **bounded exponential backoff** (configured via `AMQP_RETRY_BASE_SEC` and `AMQP_RETRY_MAX_SEC`).

**Important reliability distinction:** the database commit is atomic for the **business row + outbox row**, *not* for the database commit + RabbitMQ publication. The relay publishes **at least once** under normal recovery assumptions. If it crashes after broker confirmation but before updating `SENT`, the same event can be sent again. Consumers use `inbox.message_id` to suppress duplicate side effects.

This is a single-publisher-per-service teaching implementation. Running multiple publisher replicas safely requires row leasing/claiming, e.g. `FOR UPDATE SKIP LOCKED`, and additional failure handling.

## 4. Event processing and Accounting decision

### Happy path

1. `POST /orders`: Order inserts `APPROVAL_PENDING` and `order.created`.
2. Consumer handles `order.created`, verifies a valid customer and produces `consumer.verified`.
3. Kitchen handles `order.created`, inserts a `CREATE_PENDING` ticket and produces `kitchen.ticketCreated`.
4. Accounting collects `order.created`, `consumer.verified` and `kitchen.ticketCreated`, then evaluates the authorization rule (`amount <= 100`). On success it writes `credit_auth.status = AUTHORIZED` and `accounting.creditCardAuthorized` to its local transaction/outbox.
5. Order consumes the authorization and becomes `APPROVED`; Kitchen becomes `TICKET_ACCEPTED`.

Accounting is the **pivot-like decision point** in this educational saga, not a central orchestrator. The example does not implement a real credit card payment gateway.

### Invalid customer

Consumer emits `consumer.verificationFailed`. Accounting records `REJECTED` and publishes `accounting.creditCardAuthorizationFailed`, which causes Order to become `REJECTED` and Kitchen to reject its ticket.

### Amount over 100

The customer and kitchen can both succeed, but Accounting rejects the amount and publishes `accounting.creditCardAuthorizationFailed`. The Order and Kitchen services then move to rejected states.

The rejection state changes represent **simplified business compensation**. This lab does **not** demonstrate reversal of a real external charge, refunds or a full catalog of compensating actions.


## 5. Reliability, dead-lettering and observability

| Mechanism | Implementation |
|---|---|
| Durable topic exchange `saga` and dedicated service queues | `topology.py` and shared RabbitMQ adapter |
| Persistent event messages (`delivery_mode=2`) | Shared outbox publisher |
| Publisher confirms before `PENDING` -> `SENT` | Shared publisher; **at-least-once**, not exactly-once |
| Manual `ack` only after handler returns (DB commit) | Shared `run_consumer(...)` inbound adapter |
| Inbox deduplication using `messageId` | One inbox table per service |
| AMQP reconnection with bounded exponential backoff | Both consumer and publisher reconnect loops |
| Invalid message -> `nack(requeue=False)` -> service-specific DLQ | Durable exchange `saga.dlx`, queues `order.q.dlq`, `consumer.q.dlq`, `kitchen.q.dlq`, `accounting.q.dlq`, `audit.q.dlq` |
| Uniform `[flow]` logs including service, action, route and order ID | Shared `flow(...)` logger in the AMQP adapters |
| Multiple publishers sharing one service outbox | **Not supported**; needs row claiming / leases |

The example isolates **bad messages** in a DLQ; it does not automatically retry handler/database failures. After investigating an issue, an operator can redeliver manually. A crash after RabbitMQ confirms publication but before `SENT` is stored can produce a duplicate: inbox deduplication remains necessary. Dead lettering using classic queues is a teaching demonstration and is not an unconditional zero-loss guarantee in a clustered broker.

### DLQ vs retry: what actually happens

- **DLQ (quarantine):** the service's main queue is configured with `x-dead-letter-exchange=saga.dlx`. When the handler raises an error, the consumer uses `basic_nack(requeue=False)` and RabbitMQ routes the message to that service's `.dlq`. This is **not** an automatic retry; the message stays there until it is inspected or explicitly replayed.
- **Connection retry is different:** exponential backoff reconnects Pika after a RabbitMQ connection failure. It does **not** replay messages sitting in a DLQ. In this demo, even a *transient handler exception* goes directly to the DLQ; an operational retry/replay policy would need additional code.
- **ACK and duplicates:** successful handlers acknowledge only after the local commit. If the consumer loses its connection before acknowledging, RabbitMQ may redeliver; the service's `inbox` prevents repeated business effects. This is separate from publisher confirms, which protect the outbound relay.

### DLQ exercise: intentionally invalid message

Start the lab, then publish a message *without* a `messageId` to the `consumer.verified` route (only Accounting receives it):

```bash
make poison
make dlq
```

`accounting_service` fails validation, sends `basic_nack(requeue=False)`, and RabbitMQ routes the message to **`accounting.q.dlq`**. Open RabbitMQ Management at <http://localhost:15674>, select **Queues and Streams** -> `accounting.q.dlq`, and use **Get messages** to inspect the payload and `x-death` header. Do not click **Purge** if you want to demonstrate later inspection.

Watch the live trace:

```bash
make flow
# example lines: [flow] service=consumer_service action=received route=order.created orderId=...
#                [flow] service=accounting_service action=dead-letter route=consumer.verified ...
```

`make logs` shows complete service logs; `make flow` filters the consistent markers. A `received` entry is logged before processing, and `processed` only after commit/ack.

## 6. Run the lab

Requirements: Docker Compose, Make, curl. Run the commands from this directory.

```bash
make up
make approve
make logs
```

Available scenarios:

```bash
make approve   # valid customer, amount 42, expect APPROVED
make decline   # valid customer, amount 150, expect REJECTED
make invalid   # invalid customer, expect REJECTED
```

Use `make approve`, note the returned `orderId`, then query:

```bash
curl http://localhost:8002/orders/<orderId>
```

Endpoints and inspection tools:

- Order API: `http://localhost:8002`.
- RabbitMQ Management: `http://localhost:15674`, username `student`, password `student`.
- Adminer: <http://localhost:8082> (preselects `postgres_order`); select **System: PostgreSQL**; choose the server host and database from the table below; username `app`, password `pass`.


### Inspect all four databases using Adminer

Adminer is **already part of `docker-compose.yml`**; no external installation is needed. Each PostgreSQL instance is a separate Docker service. From the Adminer login form at <http://localhost:8082>, use **System: PostgreSQL**, **Username: `app`**, **Password: `pass`**, and select:

| Service | Adminer server | Database | Useful tables |
|---|---|---|---|
| Order | `postgres_order` | `orderdb` | `orders`, `outbox`, `inbox` |
| Consumer | `postgres_consumer` | `consumerdb` | `consumers`, `outbox`, `inbox` |
| Kitchen | `postgres_kitchen` | `kitchendb` | `tickets`, `outbox`, `inbox` |
| Accounting | `postgres_accounting` | `accountingdb` | `prereq`, `credit_auth`, `outbox`, `inbox` |

In **Adminer -> SQL command**, use the following sample queries, switching database as appropriate:

```sql
-- Order database: state after the saga completes
SELECT order_id, customer_id, amount, status FROM orders ORDER BY created_at DESC;
-- All service databases: reliable outbox and idempotency evidence
SELECT topic, status, created_at, sent_at FROM outbox ORDER BY created_at DESC;
SELECT message_id FROM inbox LIMIT 20;
-- Kitchen database: local ticket transition
SELECT order_id, status FROM tickets;
-- Accounting database: prerequisites and pivot decision
SELECT * FROM prereq;
SELECT order_id, amount, status FROM credit_auth;
```

Expected examples: `orders.status` changes from `APPROVAL_PENDING` to `APPROVED`/`REJECTED`; `tickets.status` changes from `CREATE_PENDING` to `TICKET_ACCEPTED`/`REJECTED`; `outbox.status` becomes `SENT` only after broker confirmation. **Never expect a single SQL query to join these four databases:** this lab demonstrates database-per-service.

Alternatively, use CLI logs:

```bash
make flow
make logs
```

### Broker outage exercise

```bash
docker compose stop rabbitmq
make approve
# Inspect the new order and its PENDING outbox row in Adminer.
docker compose start rabbitmq
# Inspect the row again: eventual SENT after broker publisher confirmation.
```

This experiment illustrates that **outbox persistence is independent of broker availability**. It does not prove exactly-once delivery.


### Migration note for an existing RabbitMQ container

This version sets dead-letter arguments when the durable queues are declared. **If you already started an older version of this lab, stop it and run `make reset` before `make up`** so old queue definitions do not conflict with the new arguments. `make reset` deletes the teaching databases and broker state. Save any work before doing this. A production deployment would normally use RabbitMQ policies for configurable DLX settings.

### Cleanup

```bash
make down
make reset  # deletes persisted databases and RabbitMQ data
```

## 7. Code navigation and caveats

- `*/domain/policy.py`: validation, ticket-state and authorization rules.
- `*/application/use_cases.py`: application operations and inbound event routing.
- `*/ports/repository.py`: repository contracts.
- `*/adapters/outbound/postgres_repository.py`: service-local SQLAlchemy transactions.
- `*/app.py`: FastAPI/RabbitMQ inbound adapters and composition roots.
- `libs/saga_common/saga_common/__init__.py`: shared outbox/inbox schema, polling publisher, reconnect and RabbitMQ helpers.
- `topology.py`: topic exchange and queue bindings.
- `tests/test_policies.py`: focused domain policy tests.

This is a teaching example, not a production-ready payment or saga platform. It uses PostgreSQL-specific data types and SQL constructs. Production-strength poison-message retry policies, monitoring, multi-instance publisher concurrency and real external compensation require further work.
