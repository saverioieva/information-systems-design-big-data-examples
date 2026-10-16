# Asynchronous Messaging with AMQP and RabbitMQ

This lab introduces **asynchronous communication between microservices** using RabbitMQ and its AMQP 0-9-1 messaging model.

It refactors and Dockerizes the older RabbitMQ examples used in previous editions of the course. The original examples covered RPC, publish/subscribe, direct routing, topic routing, work queues, and duplicate-message handling. This version keeps those ideas but makes the scenarios deterministic, Docker-first, and easier to execute independently.

The lab intentionally focuses on **messaging concepts** rather than on a large business application. The small FTGO-style order examples are used only to make the message flows concrete.

## Learning goals

By the end of the lab you should be able to explain and observe:

- asynchronous communication through a **message broker**;
- the difference between a **queue** and an **exchange**;
- **point-to-point / competing-consumer** processing;
- **publish/subscribe** with a queue per subscriber;
- RabbitMQ **direct, fanout, topic, and headers exchanges**;
- asynchronous **request/reply** with `reply_to` and `correlation_id`;
- **manual acknowledgements**, redelivery, and at-least-once processing;
- why consumers should often be **idempotent**;
- the relationship between **concurrency and ordering**;
- how an **AsyncAPI** document can describe a message-based contract.

---

## Architecture

All Python code runs inside Docker containers. The host only needs Docker and Docker Compose.

```text
                       RabbitMQ

 Producer        +---------------------------+        Consumer
    |            |                           |            ^
    | publish    |   Exchange --> Queue      |  deliver   |
    +----------->|      |          |         |----------->+
                 |      +--binding-+         |
                 |                           |
                 +---------------------------+
                              ^
                              |
                              +----- ACK -----+
```

A producer normally publishes to an **exchange**. The exchange does not store messages: it uses bindings and routing rules to decide which queue or queues receive a copy. Queues buffer messages until a consumer can process them.

The work-queue and request/reply examples also use RabbitMQ's **default exchange**, where a queue name is used as the routing key.

---

## How to read this project

Start with `demos/common.py`. It contains only the RabbitMQ connection and JSON serialization helpers shared by the examples.

Then read each scenario independently:

| Topic | Files to inspect | Main idea |
|---|---|---|
| Work queue | `demos/work_queue/` | one queue, competing workers, manual ACK, prefetch |
| Fanout | `demos/fanout/` | one published event copied to multiple subscriber queues |
| Direct routing | `demos/direct/` | exact routing-key matching |
| Topic routing | `demos/topic/` | wildcard routing-key matching |
| Headers routing | `demos/headers/` | routing based on message metadata |
| Request/reply | `demos/request_reply/` | request queue, reply queue, correlation ID |
| Reliability | `demos/reliability/` | redelivery and idempotent duplicate handling |
| Ordering | `demos/ordering/` | partition related events by key |
| Contract | `asyncapi/order-events.yaml` | asynchronous API contract |

The `docker-compose.yml` file is the composition root for the lab: it starts RabbitMQ and wires the scenario-specific consumers to the same Dockerized Python image.

---

## Project structure

```text
asynchronous-messaging-rabbitmq/
├── asyncapi/
│   └── order-events.yaml
├── demos/
│   ├── common.py
│   ├── work_queue/
│   ├── fanout/
│   ├── direct/
│   ├── topic/
│   ├── headers/
│   ├── request_reply/
│   ├── reliability/
│   └── ordering/
├── Dockerfile
├── docker-compose.yml
├── Makefile
├── requirements.txt
└── README.md
```

No local Python environment is required.

## Prerequisites

Required:

```text
Docker
Docker Compose
```

The `Makefile` is only a convenience layer around Docker Compose commands. No host Python, Pika, RabbitMQ CLI, or AMQP tooling is required.

Build the shared lab image once if you want to warm the Docker cache:

```bash
make build
```

Each scenario target also uses `--build`, so this explicit build step is optional.

---

# 1. Start RabbitMQ and inspect the broker

Start only the broker:

```bash
make up
```

Open the RabbitMQ Management UI:

```text
http://localhost:15672
```

Credentials:

```text
username: student
password: student
```

The AMQP port is `5672`; the management UI is exposed on `15672`.

Useful broker-side inspection commands are already wrapped by the Makefile:

```bash
make queues
make exchanges
make bindings
```

These commands execute `rabbitmqctl` **inside the RabbitMQ container**.

### What to observe

At this point RabbitMQ is running, but most application queues and exchanges do not exist yet. In the following steps, consumers declare their topology when they start.

---

# 2. Point-to-point processing with a Work Queue

Run:

```bash
make work-demo
```

The demo starts two workers and publishes eight order-processing tasks.

```text
                           orders.work
Producer  -------------------------------------------->
                         durable queue
                              |
                    +---------+---------+
                    |                   |
                    v                   v
                Worker A            Worker B
                prefetch=1          prefetch=1
                    |                   |
                    +------ ACK --------+
```

Each message is delivered to **one** worker, not to both. The workers compete for messages from the same queue.

The consumer uses:

- a **durable queue**;
- **persistent messages**;
- `prefetch_count=1` to limit the number of unacknowledged messages sent to each worker;
- a **manual acknowledgement** after processing.

This is a concrete point-to-point channel with competing consumers.

Inspect the queue while the workers are running:

```bash
make queues
```

Stop only these workers:

```bash
make work-stop
```

### Important ordering consequence

A queue has an ordered sequence of messages, but with multiple workers the **completion order** of business processing is not guaranteed. Worker A and Worker B can finish at different times.

---

# 3. Publish/Subscribe with a Fanout Exchange

Run:

```bash
make fanout-demo
```

The topology is:

```text
                       orders.fanout
Order Service  ------> [ fanout exchange ]
                              |
                    +---------+---------+
                    |                   |
                    v                   v
            inventory.events   notification.events
                    |                   |
                    v                   v
             Inventory Service   Notification Service
```

A **fanout exchange** ignores the routing key and sends a copy of the message to every bound queue.

The key detail is that publish/subscribe requires **one queue per independent subscriber**. If Inventory Service and Notification Service shared the same queue, they would compete for messages instead of each receiving a copy.

This demo uses named durable queues rather than temporary queues so you can also observe broker buffering if a consumer is stopped.

Try stopping one subscriber, publish again, inspect the queued message, and then restart the subscriber.

```bash
make fanout-stop
make fanout-up
```

---

# 4. Direct Exchange: exact routing keys

Run:

```bash
make direct-demo
```

Two events are published:

```text
order.created
order.failed
```

Bindings:

```text
                         orders.direct
                              |
              +---------------+----------------+
              |                                |
       order.created                     order.failed
              |                                |
              +-----------> audit-service <----+
                                               |
                                               +--> failure-monitor
```

`audit-service` binds its queue to both keys, while `failure-monitor` binds only to `order.failed`.

A **direct exchange** performs exact matching between the message routing key and a queue binding key.

Inspect the actual bindings:

```bash
make bindings
```

---

# 5. Topic Exchange: wildcard routing

Run:

```bash
make topic-demo
```

The demo publishes:

```text
order.created
order.updated
order.failed
```

Consumers bind using:

```text
order-history     -> order.*
onboarding-flow   -> order.created
```

Therefore:

```text
order.created  -> both consumers
order.updated  -> order-history only
order.failed   -> order-history only
```

With a topic exchange:

- `*` matches exactly one routing-key word;
- `#` matches zero or more words.

For example, a larger application could use keys such as:

```text
order.eu.created
order.us.cancelled
```

and bindings such as `order.*.created` or `order.#`.

---

# 6. Headers Exchange: route using metadata

Run:

```bash
make headers-demo
```

Three messages are published with these headers:

```text
{type=order,   region=eu}
{type=order,   region=us}
{type=payment, region=eu}
```

The two consumers are configured as:

```text
eu-order-handler  -> type=order AND region=eu
payment-handler   -> type=payment
```

Unlike direct and topic exchanges, a **headers exchange** ignores the routing key and evaluates message header values.

This is useful when routing depends on several metadata attributes rather than on one hierarchical string.

---

# 7. Asynchronous Request/Reply

Start the RPC-style server and execute two calls:

```bash
make rpc-demo
```

The transport is still asynchronous messaging even though the client chooses to wait for the response.

```text
Client
  |
  | request
  | correlation_id = X
  | reply_to = callback queue
  v
pricing.rpc queue
  |
  v
Pricing Service
  |
  | reply correlation_id = X
  v
callback queue
  |
  v
Client matches X
```

The client creates an exclusive callback queue and sends its name in `reply_to`. A unique `correlation_id` identifies the request. The service copies the same ID into the reply so the client can match responses to requests.

This pattern is useful when request/reply semantics are needed over a broker, but it also reintroduces some temporal coupling if the caller blocks waiting for the answer.

---

# 8. Redelivery and manual acknowledgements

Run the deterministic crash demo:

```bash
make redelivery-demo
```

The sequence is:

```text
1. publish one persistent message
2. consumer receives it
3. consumer crashes BEFORE ACK
4. RabbitMQ requeues the unacknowledged message
5. a new consumer receives the same message again
6. the second consumer ACKs it
```

The second delivery prints:

```text
redelivered=True
```

This demonstrates why message handlers must be prepared for **at-least-once delivery**. A broker cannot always know whether the application completed its side effect before a crash occurred.

An acknowledgement is therefore not the same thing as "exactly once" business processing.

---

# 9. Idempotent Consumer and duplicate messages

Run:

```bash
make duplicate-demo
```

The publisher intentionally sends the same `message_id` twice, then sends one new message.

The consumer stores processed IDs in SQLite inside a Docker volume:

```text
message arrives
      |
      v
is message_id already stored?
      |
  +---+---+
  |       |
 no      yes
  |       |
process  skip
  |       |
store ID  |
  +---+---+
      |
     ACK
```

This is the **Idempotent Consumer** pattern. The duplicate delivery is acknowledged but its business effect is not executed again.

The database is infrastructure for the teaching example; in a real service the processed-message record normally needs transaction semantics compatible with the business update it protects.

To remove the SQLite state and all RabbitMQ data:

```bash
make reset
```

---

# 10. Ordering by key

Run:

```bash
make ordering-demo
```

The publisher interleaves events for two orders:

```text
A1 B1 A2 B2 A3 B3
```

A direct exchange partitions them using the order key:

```text
                       orders.partitioned
                              |
                   +----------+----------+
                   |                     |
               order.A                 order.B
                   |                     |
                   v                     v
          orders.partition.a     orders.partition.b
                   |                     |
                   v                     v
             Consumer A             Consumer B

              A1 A2 A3              B1 B2 B3
```

The example does **not** claim that RabbitMQ provides global ordering across independently processed queues. Instead, it demonstrates a common strategy: route related messages with the same key to the same ordered processing path.

The design principle is:

> If order matters, define the scope in which it must be preserved.

For many business systems, per-order or per-aggregate ordering is more useful than one global sequence.

---

# 11. AsyncAPI: describe the asynchronous contract

Open:

```text
asyncapi/order-events.yaml
```

The file describes a minimal `OrderCreated` contract using AsyncAPI 3.0 concepts:

```text
Server
  -> where the broker is

Channel
  -> logical communication path

Message
  -> headers/payload contract

Operation
  -> send or receive
```

The important architectural analogy is:

```text
REST                         Messaging
----                         ---------
OpenAPI                      AsyncAPI
HTTP endpoint                Channel
request/response schema      Message schema
operation                    send/receive operation
```

The AsyncAPI file is deliberately kept independent from the Python implementation. It is a **contract**, not the message handler itself.

RabbitMQ-specific topology such as exchange type, queue names, and bindings is shown explicitly in the executable demos and can also be represented with protocol bindings in a richer AsyncAPI document.

---

## RabbitMQ concepts mapped to this lab

| Concept | In this lab |
|---|---|
| Producer | one-shot Dockerized publisher scripts |
| Message | JSON body + AMQP properties/headers |
| Exchange | `orders.fanout`, `orders.direct`, `orders.topic`, `orders.headers`, ... |
| Binding | rules connecting exchanges to queues |
| Queue | durable buffers such as `orders.work` or `inventory.events` |
| Consumer | long-running Dockerized Python services |
| ACK | sent manually after successful processing in reliability-sensitive demos |
| Routing key | used by direct/topic exchanges |
| Message headers | used by the headers exchange and message IDs |
| Prefetch | limits outstanding work in the work-queue example |

---

## Why the examples use JSON

AMQP transports bytes. RabbitMQ does not require JSON: the body could contain JSON, Protobuf, Avro, text, or another binary format.

The lab uses JSON because the focus is on **messaging topology and delivery semantics**, not serialization performance.

The AMQP message properties remain separate from the body and are used for metadata such as:

```text
message_id
correlation_id
reply_to
content_type
custom headers
```

---

## Broker-based messaging and availability

Asynchronous broker-based communication reduces direct temporal coupling:

```text
Synchronous call
Service A ---> Service B
               must be available now

Asynchronous messaging
Service A ---> RabbitMQ ---> Service B
                 |
                 +-- can buffer while B is unavailable
```

This does not make failures disappear. RabbitMQ itself becomes infrastructure that must be operated reliably, and applications must handle delayed delivery, duplicate delivery, poison messages, back pressure, schema evolution, and observability.

---

## Useful classroom sequence

A compact walkthrough is:

```text
RabbitMQ Management UI
        |
        v
Work Queue
point-to-point + ACK + prefetch
        |
        v
Fanout
publish/subscribe
        |
        v
Direct / Topic / Headers
routing policies
        |
        v
Request/Reply
reply_to + correlation_id
        |
        v
Redelivery
crash before ACK
        |
        v
Idempotent Consumer
duplicate message ID
        |
        v
Ordering by key
partitioned processing
        |
        v
AsyncAPI
message contract
```

This sequence moves from the broker topology to the delivery guarantees and finally to the API contract.

---

## Stop and clean up

Stop the complete lab while keeping RabbitMQ and SQLite volumes:

```bash
make down
```

Remove containers **and all persisted demo state**:

```bash
make reset
```

Use `make reset` before a fresh classroom run if you want a completely clean broker.

---

## Notes on the previous examples

The older examples in `microservices_examples.zip` were used as the starting point for this lab:

- `rabbit-mq/rpc/` -> request/reply;
- `rabbit-mq/pubsub/` -> fanout publish/subscribe;
- `rabbit-mq/routing/` -> direct exchange;
- `rabbit-mq/topic/` -> topic exchange;
- `rabbit-mq/workers/` -> work queue, prefetch, and acknowledgements;
- `rabbit-mq/duplicate/` -> idempotent duplicate handling.

The old `finish-processing/` example is intentionally not folded into this lab. It mixes asynchronous messaging with multi-service workflow coordination, which is better treated separately when introducing sagas and distributed transaction patterns.

The new version changes the execution model in three important ways:

1. **everything runs in Docker**;
2. each scenario has deterministic inputs instead of random/infinite publishers;
3. the README separates the messaging concepts from implementation code so the code can be inspected after the behavior is understood.
