# Create Order Saga — Orchestration (State Machine)

A new lab for the **Orchestration-Based Saga**, **Saga State Machine**, **Compensating Transactions**, **Semantic Lock**, and **Lack of Isolation** slides.

## Is an orchestration framework used?

**No.** The orchestration logic is deliberately implemented in plain Python, **not** Temporal, Camunda, or another workflow/saga framework. `app/domain/transitions.py` holds an explicit state-transition table; `SagaUseCases._reply()` selects the next command, and the `sagas` SQLite table stores the current state. RabbitMQ transports commands/replies; it is **not** the orchestrator. This directly demonstrates the **orchestrator class + state machine** concepts from the slides. A production workflow engine can add timers, history, retries and operational tools, but **that is beyond this chapter's lab scope**.

The **Orchestrator** controls a sequence of asynchronous *commands*, while participants send *replies*. Participants do not know the saga sequence. This is intentionally a different coordination style from the choreography lab.

## Architecture

```text
POST /orders
      |
      v
Order/Orchestrator (SQLite: orders + sagas + inbox + outbox)
      |
      +-- VerifyConsumer  --> Consumer --> ConsumerVerified / ConsumerRejected
      |
      +-- CreateTicket    --> Kitchen  --> TicketCreated
      |
      +-- AuthorizeCard   --> Accounting --> CardAuthorized / CardDeclined
      |                                           |
      |          +--------------------------------+ failure
      |          v
      +-- RejectTicket    --> Kitchen --> TicketRejected --> Order REJECTED
      |
      +-- ApproveTicket   --> Kitchen --> TicketApproved --> Order APPROVED
```

Every participant writes its **own SQLite database file** in a separate Docker volume; the orchestrator persists `sagas.stage`. All commands and replies travel through RabbitMQ's durable `saga.transport` exchange and durable queues. Each role persists new outbox messages in the same transaction as its local changes, and an independent thread polls the outbox and publishes with confirms.

This is a **teaching implementation**, not a production payment platform. `AuthorizeCard` is simulated: amounts `<= 100` succeed, amounts `> 100` fail. Compensation is a *business action* (`RejectTicket`), not a distributed SQL rollback.

## Run

Prerequisites: Docker Compose, Make, curl. Ports: API `8001`, RabbitMQ UI `15673` (`student` / `student`).

```bash
make up
make approve
make logs
```

The `make approve` output gives `orderId`. Inspect the state with:

```bash
curl http://localhost:8001/orders/<orderId>
```

After asynchronous processing completes, expect `status=APPROVED` and `stage=APPROVED`.

### Demo 1 — Happy path

```bash
make approve
```

Trace `VERIFY_CONSUMER` → `CREATE_TICKET` → `AUTHORIZE_CARD` → `APPROVE_TICKET` → `APPROVED` in the logs. Inspect `app/domain/transitions.py` and `app/application/use_cases.py`.

### Demo 2 — Compensating transaction

```bash
make decline
```

The Accounting Service rejects an amount of `150`; the orchestrator enters `REJECT_TICKET`, sends `RejectTicket`, waits for `TicketRejected`, and marks the order `REJECTED`.

### Demo 3 — Rejection before creating a ticket

```bash
make invalid
```

`CUST_INVALID` is rejected by the Consumer Service, so the saga ends without creating a kitchen ticket. Explain why not every failure requires the same compensation.

### Demo 4 — Waiting for an unavailable participant

```bash
docker compose stop kitchen
make approve
# Observe GET /orders/<orderId>: stage should eventually be CREATE_TICKET.
docker compose start kitchen
# The command remains queued; the saga can resume.
```

**Important:** pre-created queues exist before any service sends commands (see `app/topology.py` and the `setup` service in Compose). Messages use manual consumer acknowledgments and unique IDs stored in an inbox table to avoid duplicate side effects. The state machine ignores stale replies not valid for its current state.

### Code reading order — hexagonal design

| File | What to inspect |
|---|---|
| `app/domain/transitions.py` | Pure state-machine transitions and compensation paths |
| `app/domain/policy.py` | Pure consumer and card authorization policies |
| `app/application/use_cases.py` | Saga coordinator, command handling and reply handling |
| `app/ports/storage.py` | Database transaction interfaces required by the application |
| `app/adapters/outbound/sqlite_store.py` | Local SQLite transaction, inbox, outbox and domain state |
| `app/adapters/outbound/rabbitmq_transport.py` | AMQP publisher with confirms |
| `app/adapters/inbound/rabbitmq_consumer.py` | Incoming commands/replies and acknowledgments |
| `app/main.py` | HTTP adapter, composition root and relay loop |
| `app/topology.py` | Queue provisioning |

### Isolation and semantic locks

`APPROVAL_PENDING` is a **semantic lock**: other business operations should refuse or defer changes while the saga is incomplete. This lab demonstrates the state but does not implement a second Cancel Order Saga. A useful extension is to add `POST /orders/{id}/cancel` with a conditional update requiring `status='APPROVAL_PENDING'` or a more explicit cancellation policy, and explore concurrent Create/Cancel.

### Limitations

- Local SQLite databases are simple teaching persistence, not recommended for horizontally scaled services; PostgreSQL is a more realistic choice at scale.
- One relay per service; concurrent multi-instance relays require outbox leasing/locking.
- No retry/poison-message policy, timeouts or monitoring dashboard beyond logs. Permanent handler errors are rejected, rather than endlessly requeued.
- Accounting uses a simulated authorization and cannot reverse an external payment. Real pivots, compensations and security need explicit domain design.
- An eventual consistency design needs these operational safeguards in production. **Do not interpret this demo as a guarantee of globally ACID transactions or exactly-once delivery.**

## Cleanup

```bash
make down
make reset  # WARNING: deletes volumes and state
```
