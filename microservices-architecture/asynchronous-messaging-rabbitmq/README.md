# Asynchronous Messaging with AMQP and RabbitMQ

This lab introduces **asynchronous messaging between microservices**, focusing on RabbitMQ message routing with **AMQP 0-9-1**, then closing with a hands-on **AMQP 1.0** example using Apache Qpid Proton and the same RabbitMQ 4.x broker.

The examples are Docker-first: the host only needs Docker, Docker Compose, and `make`. No local Python, Pika, Proton, RabbitMQ CLI, or AMQP tooling is required.

The lab deliberately separates **long-running services/consumers** from **one-shot publishers/clients**. This makes the message flow visible in class: first start the services, keep their logs open, then publish messages from a second terminal.

## Learning goals

By the end of the lab you should be able to explain and observe:

- asynchronous communication through a **message broker**;
- the difference between **AMQP 0-9-1**, **AMQP 1.0**, and the RabbitMQ product;
- the difference between a **queue** and an **exchange**;
- **point-to-point / competing-consumer** processing;
- **publish/subscribe** with a queue per subscriber;
- RabbitMQ **direct, fanout, topic, and headers exchanges**;
- asynchronous **request/reply** with `reply_to` and `correlation_id`;
- **manual acknowledgements**, redelivery, and at-least-once processing;
- why consumers should often be **idempotent**;
- the relationship between **concurrency and ordering**;
- how an **AsyncAPI** document can describe a message-based contract;
- how an **AMQP 1.0 sender and receiver** use Proton links, messages, and settlement;
- how RabbitMQ can bridge a **Pika/0-9-1 publisher** to a **Proton/1.0 consumer**.

---

## How this lab follows the lecture slides

The practical steps follow the sequence **messaging and broker → AMQP versions → RabbitMQ exchanges → work queues → publish/subscribe → request/reply → reliability and ordering → AsyncAPI → AMQP 1.0 in Python**.

| Lecture topic | In this lab |
|---|---|
| Why use a broker? | Section 1, RabbitMQ UI, queue/broker inspection |
| AMQP evolution and protocol choice | Concept notes below; final Proton exercise in Section 12 |
| RabbitMQ message flow; direct/topic/headers exchanges | Sections 2–4 (fanout appears in the pub/sub exercise) |
| Point-to-point and work queues | Section 5 |
| Publish/subscribe | Section 6, fanout |
| Request/reply | Section 7 |
| Duplicates, redelivery, ordering | Sections 8–10 |
| AsyncAPI | Section 11 |
| AMQP 1.0 on RabbitMQ with Python | Section 12 |

**Kafka connection to the slides:** Kafka's partitioned event-log model differs from the classic queues used here. Kafka is **not installed** in this RabbitMQ-focused lab; there is no Kafka practical exercise.

### Why a broker?

In direct messaging the producer must locate the receiver, and receiver outages need handling by the producer. A broker separates producers from consumers and can buffer messages during temporary outages. That introduces infrastructure that needs monitoring, high availability, capacity planning, and attention to eventual consistency, retries, and duplicates.

### AMQP versions and their relationship to RabbitMQ

- **AMQP** means **Advanced Message Queuing Protocol**.
- **AMQP 0-9-1** prescribes exchange, binding, queue, and routing-key concepts. In Sections 1–11 the Python client is **Pika**.
- **AMQP 1.0** is an independent OASIS/ISO standard centered on transport concepts (connections, sessions, sender/receiver links, flow credit, message transfer, and delivery settlement). It is **not wire-compatible** with AMQP 0-9-1.
- **RabbitMQ 4.x supports both protocols natively on the same TCP port (5672)**. The final example uses **Qpid Proton** to speak AMQP 1.0 to that same broker.
- RabbitMQ-specific AMQP 1.0 **v2 addresses** such as `/queues/orders.amqp10` represent the broker's queues. AMQP 1.0 itself does not prescribe an internal broker topology. The queue must already exist.
- Pika is used **only for the topology preparation and optional cross-protocol publisher** in the final exercise; the final producer and consumer both send/receive using Proton/AMQP 1.0.

Official references: [RabbitMQ AMQP 1.0](https://www.rabbitmq.com/docs/amqp), [Qpid Proton Python API](https://qpid.apache.org/releases/qpid-proton-0.40.0/proton/python/docs/), [AMQP 1.0 OASIS standard](https://www.oasis-open.org/standard/amqp/).

---

## Architecture

```text
                       RabbitMQ

 Publisher       +---------------------------+        Consumer
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

## Two Makefiles, two roles

The project has intentionally been split into two active Makefiles (`Makefile.services` and `Makefile.publishers`). The original single `Makefile` remains in the folder for backward compatibility, but this README follows the two-terminal flow.

```text
Makefile.services
    |
    +-- RabbitMQ
    +-- long-running consumers/workers
    +-- service logs and broker inspection

Makefile.publishers
    |
    +-- one-shot publishers
    +-- request/reply clients
    +-- deterministic message generation
    +-- Proton AMQP 1.0 publisher (final exercise)
```

The normal classroom workflow uses **two terminals**.

### Terminal 1 — start the service side

For example:

```bash
make -f Makefile.services fanout
make -f Makefile.services fanout-logs
```

The first command starts RabbitMQ and the fanout consumers. It waits until the consumers have declared their queues before returning.

The second command follows the consumer logs.

### Terminal 2 — send messages

```bash
make -f Makefile.publishers fanout
```

Run the publisher target again whenever you want to send another deterministic batch of messages.

> The publisher Makefile does **not** start RabbitMQ or consumers implicitly. Services must be running first.

This separation is intentional: it makes the asynchronous nature of the examples easier to observe than a single target that starts services, publishes messages, waits, and prints logs in sequence.

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
│   ├── ordering/
│   └── amqp10/                 # Proton AMQP 1.0 + Pika setup
├── Dockerfile                # Pika image for existing demos
├── Dockerfile.amqp10         # Separate Qpid Proton image
├── docker-compose.yml
├── Makefile.services
├── Makefile.publishers
├── Makefile                 # legacy one-terminal targets (unchanged)
├── requirements.txt
└── README.md
```

`docker-compose.yml` is the composition root. All Pika demos use the original Python image. The new AMQP 1.0 example uses a **separate Proton image** to avoid changing existing demo dependencies. Both connect to the **same RabbitMQ broker**.

## How to read the source code

The examples intentionally keep the Python small so that each messaging concept is visible in one publisher and one consumer. A useful reading order is:

```text
docker-compose.yml
      |
      | selects a scenario through Compose profiles
      | and injects queue names / binding keys / consumer names
      v
demos/<scenario>/consumer.py      long-running service side
      ^
      | RabbitMQ exchange / queue / binding
      v
demos/<scenario>/publisher.py     one-shot producer side
```

Start with these shared files:

| File | What to notice |
|---|---|
| `demos/common.py` | Creates the Pika connection, retries while RabbitMQ starts, encodes/decodes JSON, and creates persistent AMQP properties. |
| `docker-compose.yml` | Runs one RabbitMQ broker and parameterizes reusable consumer modules with environment variables. Compose profiles keep scenarios independent. |
| `Makefile.services` | Owns the lifecycle of RabbitMQ and long-running consumers. It waits for expected queues so a publisher is not started before the topology exists. |
| `Makefile.publishers` | Runs one-shot publishers/clients in disposable containers. It deliberately does not start consumers. |
| `demos/amqp10/setup.py` | Declares `orders.amqp10` via Pika before Proton attaches to `/queues/orders.amqp10`. |
| `demos/amqp10/publisher.py`, `consumer.py` | Send and receive over AMQP 1.0 with Qpid Proton; explicitly settle messages. |
| `Dockerfile.amqp10` | Installs the AMQP 1.0 client without changing the original Pika image. |
| `asyncapi/order-events.yaml` | Documents one asynchronous contract independently from the Python implementation. |

### Shared Pika helper: `demos/common.py`

All **AMQP 0-9-1 / Pika** examples use the same helper instead of repeating connection boilerplate. In particular:

- `connection()` reads RabbitMQ coordinates from environment variables and retries the initial connection;
- `encode()` / `decode()` keep the payload examples as JSON bytes;
- `persistent_json_properties()` sets `content_type=application/json` and `delivery_mode=2`, and can add AMQP properties such as `message_id`, `correlation_id`, `reply_to`, or custom headers.

This helper is infrastructure code for the Pika demos; it is not a domain abstraction. The goal is simply to keep each scenario focused on the AMQP concept being demonstrated.

### Where the messaging topology is declared

RabbitMQ topology is created with idempotent declarations such as `exchange_declare()`, `queue_declare()`, and `queue_bind()`. Most consumers declare the topology they need when they start. Publishers also declare the exchange or queue they publish to so that a standalone publisher fails less mysteriously if the broker was reset.

The important distinction is:

```text
exchange_declare()  -> creates/configures the routing entity
queue_declare()     -> creates/configures the buffer
queue_bind()        -> connects a queue to an exchange using a rule
basic_publish()     -> sends a message
basic_consume()     -> registers a consumer callback
basic_ack()         -> confirms successful processing of one delivery
```

---

## Prerequisites

Required:

```text
Docker
Docker Compose
GNU Make
```

Optional warm-up build:

```bash
make -f Makefile.services build
```

Each service target also uses `--build`, so this explicit build step is not required.

Useful help:

```bash
make -f Makefile.services help
make -f Makefile.publishers help
```

---

# 1. Start RabbitMQ and inspect the broker

Start only RabbitMQ:

```bash
make -f Makefile.services broker
```

RabbitMQ Management UI:

```text
http://localhost:15672
```

Credentials:

```text
username: student
password: student
```

Useful inspection commands:

```bash
make -f Makefile.services status
make -f Makefile.services queues
make -f Makefile.services exchanges
make -f Makefile.services bindings
```

At this point RabbitMQ is running, but most application queues and exchanges do not exist yet. In the following steps the consumers declare the topology when they start.

---

# 2. Direct Exchange: exact routing keys

The exchange is the entry point for a published message; **bindings** decide which queues receive it. Exchange types covered in the following exercises are **direct**, **fanout**, **topic**, and **headers**. The fanout example is placed after the work queue to align with the lecture's publish/subscribe section.

## Terminal 1 — start consumers

```bash
make -f Makefile.services direct
make -f Makefile.services direct-logs
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

## Terminal 2 — publish events

```bash
make -f Makefile.publishers direct
```

The publisher sends one `order.created` event and one `order.failed` event.

A **direct exchange** performs exact matching between the message routing key and queue binding keys.

Inspect the bindings:

```bash
make -f Makefile.services bindings
```

### Source code to inspect

- `demos/direct/publisher.py` chooses the routing key (`order.created` or `order.failed`) and passes it to `basic_publish()`.
- `demos/direct/consumer.py` reads `BINDING_KEYS` from the environment and creates one binding for each key.
- `audit-service` is bound to both keys, while `failure-monitor` is bound only to `order.failed`. Both containers execute the **same Python consumer module** with different configuration.

This is useful to distinguish the **message routing key** carried at publish time from the **binding keys** configured on queues.

---

# 3. Topic Exchange: wildcard routing

## Terminal 1 — start consumers

```bash
make -f Makefile.services topic
make -f Makefile.services topic-logs
```

Consumers bind with:

```text
order-history     -> order.*
onboarding-flow   -> order.created
```

## Terminal 2 — publish events

```bash
make -f Makefile.publishers topic
```

The publisher sends:

```text
order.created
order.updated
order.failed
```

Expected routing:

```text
order.created  -> both consumers
order.updated  -> order-history only
order.failed   -> order-history only
```

With a topic exchange:

- `*` matches exactly one routing-key word;
- `#` matches zero or more words.

### Source code to inspect

- `demos/topic/publisher.py` publishes the same message shape with different routing keys.
- `demos/topic/consumer.py` has a single `BINDING_KEY`, provided by Compose.
- `order-history` uses `order.*`; `onboarding-flow` uses the exact pattern `order.created`.

The exchange performs pattern matching; consumers do not receive every message and then filter in Python. Non-matching messages are never routed to their queues.

---

# 4. Headers Exchange: route using metadata

## Terminal 1 — start consumers

```bash
make -f Makefile.services headers
make -f Makefile.services headers-logs
```

Consumers are configured as:

```text
eu-order-handler  -> type=order AND region=eu
payment-handler   -> type=payment
```

## Terminal 2 — publish messages

```bash
make -f Makefile.publishers headers
```

The publisher sends:

```text
{type=order,   region=eu}
{type=order,   region=us}
{type=payment, region=eu}
```

Unlike direct and topic exchanges, a **headers exchange** ignores the routing key and evaluates AMQP header values.

### Source code to inspect

- `demos/headers/publisher.py` places `type` and `region` in `BasicProperties.headers`. The routing key is intentionally set to `ignored.by.headers.exchange`.
- `demos/headers/consumer.py` builds the binding arguments as `{"x-match": "all", ...}`. Therefore all configured headers must match.
- Compose injects different `BINDING_HEADERS` JSON values for `eu-order-handler` and `payment-handler`.

Changing `x-match` from `all` to `any` would change the semantics: one matching header would be sufficient. The current lab uses `all` to keep the routing rule deterministic.

---

# 5. Point-to-point processing with a Work Queue

## Terminal 1 — start two workers

```bash
make -f Makefile.services work
make -f Makefile.services work-logs
```

Topology:

```text
                           orders.work
Publisher  -------------------------------------------->
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

## Terminal 2 — publish work

```bash
make -f Makefile.publishers work
```

Eight order-processing tasks are published. Each message is delivered to **one** worker, not to both. The workers compete for messages from the same queue.

The consumers use:

- a **durable queue**;
- **persistent messages**;
- `prefetch_count=1`;
- a **manual acknowledgement** after processing.

Inspect the queue while workers are processing:

```bash
make -f Makefile.services queues
```

Stop only the workers:

```bash
make -f Makefile.services work-stop
```

### Source code to inspect

- `demos/work_queue/publisher.py` publishes to the **default exchange** (`exchange=""`) using `orders.work` as the routing key; with the default exchange, that routing key is the queue name.
- `demos/work_queue/worker.py` declares the same durable queue, uses `basic_qos(prefetch_count=1)`, processes one delivery, then calls `basic_ack()`.
- `WORKER_NAME` comes from `docker-compose.yml`, allowing the same worker code to run as `worker-a` and `worker-b`.

`prefetch_count=1` is important for the demo: RabbitMQ does not give a worker a second unacknowledged task while it is still processing the first one. This makes the competing-consumer behavior easy to observe.

### Ordering consequence

A queue has an ordered sequence of messages, but with multiple workers the **completion order** of business processing is not guaranteed.

---

# 6. Publish/Subscribe with a Fanout Exchange

## Terminal 1 — start subscribers

```bash
make -f Makefile.services fanout
make -f Makefile.services fanout-logs
```

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

## Terminal 2 — publish an event

```bash
make -f Makefile.publishers fanout
```

A **fanout exchange** ignores the routing key and sends a copy of the message to every bound queue.

The important detail is that publish/subscribe requires **one queue per independent subscriber**. If both services consumed the same queue, they would compete for messages instead of each receiving a copy.

Because the queues are durable, you can stop consumers, publish again, inspect the buffered message, and restart the consumers.

### Source code to inspect

- `demos/fanout/publisher.py` publishes one `OrderCreated` event to `orders.fanout` with an empty routing key because a fanout exchange ignores it.
- `demos/fanout/consumer.py` is reused by both subscribers. `QUEUE_NAME` and `CONSUMER_NAME` are injected by Compose.
- Each consumer declares **its own queue** and binds it to the same exchange. That queue-per-subscriber detail is what turns the topology into publish/subscribe.

Notice that the publisher does not know how many subscribers exist. Adding another subscriber means adding another queue/binding; the publisher does not change.

---

# 7. Asynchronous Request/Reply

## Terminal 1 — start the pricing service

```bash
make -f Makefile.services rpc
make -f Makefile.services rpc-logs
```

## Terminal 2 — run the clients

```bash
make -f Makefile.publishers rpc
```

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

The transport is asynchronous messaging even though the example client chooses to wait for the response.

The client creates an exclusive callback queue and sends its name in `reply_to`. A unique `correlation_id` identifies the request. The service copies the same ID into the reply so the client can match responses to requests.

### Source code to inspect

- `demos/request_reply/client.py` declares a server-named, exclusive, auto-delete callback queue. It publishes the request with both `reply_to` and `correlation_id`.
- The client registers a callback on that reply queue and ignores replies whose `correlation_id` does not match the outstanding request.
- `demos/request_reply/server.py` consumes `pricing.rpc`, calculates the response, publishes it to `properties.reply_to`, copies `properties.correlation_id`, and only then ACKs the request.

The example is intentionally **synchronous from the caller's point of view** because the loop waits until a matching response arrives. The underlying transport is still asynchronous messaging. A production client could instead continue other work and handle replies later.

---

# 8. Redelivery after a consumer crash

This example is intentionally split into **three explicit actions** so that the broker behavior is visible.

## Terminal 1 — start a consumer that will crash before ACK

```bash
make -f Makefile.services redelivery-crash
make -f Makefile.services redelivery-crash-logs
```

The consumer is now waiting on `reliability.redelivery`.

## Terminal 2 — publish one persistent message

```bash
make -f Makefile.publishers redelivery
```

The first consumer receives the message and terminates **before acknowledging it**.

Inspect the stopped consumer and queue state if desired:

```bash
make -f Makefile.services status
make -f Makefile.services queues
```

## Terminal 1 — start the recovery consumer

```bash
make -f Makefile.services redelivery-recover
make -f Makefile.services redelivery-recover-logs
```

The second delivery prints:

```text
redelivered=True
```

Sequence:

```text
publish
   |
   v
consumer receives
   |
   v
crash before ACK
   |
   v
RabbitMQ requeues
   |
   v
new consumer receives same message
   |
   v
ACK
```

This demonstrates **at-least-once delivery**. An acknowledgement is not the same thing as exactly-once business processing.

### Source code to inspect

- `demos/reliability/redelivery_publisher.py` publishes one persistent message and assigns a `message_id`. It purges the demo queue first so the classroom run starts from a known state.
- `demos/reliability/redelivery_consumer.py --crash-before-ack` calls `os._exit(3)` after receiving the delivery but before `basic_ack()`. This deliberately terminates the process without giving the broker an ACK.
- The recovery consumer runs the same module without the crash flag and prints `method.redelivered`.

RabbitMQ redelivery means **the broker did not observe an acknowledgement for the previous delivery**. It does not prove that the previous consumer performed no business side effect before crashing. This is why at-least-once delivery and idempotent processing must be considered together.

---

# 9. Idempotent Consumer and duplicate messages

## Terminal 1 — start the idempotent consumer

```bash
make -f Makefile.services duplicate
make -f Makefile.services duplicate-logs
```

## Terminal 2 — publish deliberate duplicates

```bash
make -f Makefile.publishers duplicate
```

The publisher sends the same `message_id` twice and then sends one unique message.

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

The consumer stores processed IDs in SQLite inside a Docker volume. Duplicate delivery is acknowledged, but the business effect is not executed again.

### Source code to inspect

- `demos/reliability/duplicate_publisher.py` deliberately sends the same `message_id` twice, then sends a different ID.
- `demos/reliability/idempotent_consumer.py` uses `message_id` as the primary key of `processed_messages` in SQLite.
- On a duplicate, the consumer skips the simulated business action but still ACKs the delivery so RabbitMQ can remove it.

The SQLite table is a teaching version of an **inbox / processed-message store**. In a real service, the business update and the record that marks a message as processed should be coordinated carefully (often in the same local database transaction when possible). The example does not claim distributed exactly-once delivery.

---

# 10. Ordering by key

## Terminal 1 — start partition consumers

```bash
make -f Makefile.services ordering
make -f Makefile.services ordering-logs
```

## Terminal 2 — publish interleaved events

```bash
make -f Makefile.publishers ordering
```

The publisher emits:

```text
A1 B1 A2 B2 A3 B3
```

A direct exchange partitions messages using the order key:

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

The example does **not** claim global ordering across independently processed queues. It demonstrates a common strategy: route related messages with the same key to the same ordered processing path.

> If order matters, define the scope in which it must be preserved.

### Source code to inspect

- `demos/ordering/publisher.py` emits interleaved events for orders A and B, but routes them with `order.A` and `order.B`.
- `demos/ordering/consumer.py` derives its queue and routing key from `ORDER_KEY`. Compose starts one instance for A and one for B.
- Each key therefore has one queue and one consumer path in this demo, preserving the sequence within that partition.

The ordering guarantee shown here is **per key / per queue**, not global. If several consumers were attached to the same partition queue and processed concurrently, completion order could diverge again.

---

# 11. AsyncAPI: describe the asynchronous contract

Open:

```text
asyncapi/order-events.yaml
```

The document uses AsyncAPI 3.0 concepts:

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

Architectural analogy:

```text
REST                         Messaging
----                         ---------
OpenAPI                      AsyncAPI
HTTP endpoint                Channel
request/response schema      Message schema
operation                    send/receive operation
```

The contract is deliberately independent from the Python implementation.

### Source code to inspect

`asyncapi/order-events.yaml` documents the `OrderCreated` message on the logical `orders.topic` channel. It describes:

- the RabbitMQ server;
- the channel address;
- the message payload schema;
- one `send` operation and one `receive` operation.

The Python examples do **not** generate code from this file and do not validate runtime messages against it. In this lab AsyncAPI is used as a contract/documentation artifact, analogous to the role OpenAPI played in the REST examples. A later extension could introduce contract validation or code generation without changing the messaging concepts demonstrated here.

---

# 12. AMQP 1.0 on RabbitMQ with Apache Qpid Proton (Python)

This is the **final hands-on example**. It shows how RabbitMQ 4.x supports **both AMQP 0-9-1 and AMQP 1.0** on the same broker (port **5672**), despite the protocols being **not wire-compatible**. All previous hands-on chapters used **Pika/AMQP 0-9-1**. Here the sender and receiver use **Apache Qpid Proton / AMQP 1.0**.

## Topology and protocol boundary

```text
Pika / AMQP 0-9-1              RabbitMQ 4.x                 Proton / AMQP 1.0
(setup only)              (one broker, port 5672)           (send + receive)
     |                            |                                |
     +---- queue_declare() ------>+ orders.amqp10                   |
                                  |                                |
Proton AMQP 1.0 publisher ------>+ /queues/orders.amqp10 -------->+ Proton consumer
                                  |                                +-- receiver.accept()
Optional Pika 0-9-1 publisher -->+ (cross-protocol conversion) -->+ same Proton consumer
```

**Important:** `/queues/orders.amqp10` is the **RabbitMQ AMQP 1.0 v2 address format**, not a universal AMQP 1.0 address. The queue must exist **before** Proton creates sender/receiver links. In this example it is declared with Pika, demonstrating the difference between RabbitMQ's queue topology and the AMQP 1.0 transfer protocol. For production AMQP 1.0 applications, use an appropriate topology management tool or supported client management API instead of coupling setup to Pika.

## Terminal 1 — start the service side

```bash
make -f Makefile.services amqp10
make -f Makefile.services amqp10-logs
```

The first command does four things in order:

1. Starts the existing RabbitMQ 4.x broker.
2. Builds the original Pika `lab` container.
3. Runs `demos/amqp10/setup.py` (Pika/AMQP 0-9-1) to declare durable queue `orders.amqp10`.
4. Builds/starts the **separate Proton consumer** using `Dockerfile.amqp10`.

The Proton image builds the upstream `python-qpid-proton==0.40.0` source distribution. **Its first Docker build can take longer** than the existing Pika image because it compiles native dependencies.

## Terminal 2 — publish via AMQP 1.0

```bash
make -f Makefile.publishers amqp10
```

This runs `demos/amqp10/publisher.py` using **Qpid Proton**, sending three JSON order events through `sender.send()` to `/queues/orders.amqp10`. The receiver in Terminal 1 uses `receiver.receive()` and, after processing, explicitly calls `receiver.accept()`, which settles the delivery.

**Observe:** the sender's successful settlement indicates that the **broker accepted the transfer**, not that the application consumer completed processing. The **receiver's `accept()`** is a separate outcome.

## Optional — prove cross-protocol interoperability

With the same Proton consumer running, publish another event using **Pika/AMQP 0-9-1**:

```bash
make -f Makefile.publishers amqp10-pika
```

The same Proton AMQP 1.0 consumer prints a message with `"source": "pika-amqp-0-9-1"`. RabbitMQ bridges messages between clients using different protocols; the clients are **not connecting directly to each other**, and AMQP 0-9-1 and 1.0 are **not wire-compatible**.

### Source code to inspect

| File | What students should notice |
|---|---|
| `demos/amqp10/setup.py` | Predeclares the durable RabbitMQ queue with Pika/AMQP 0-9-1. |
| `demos/amqp10/settings.py` | Proton connection, SASL credentials, and RabbitMQ-specific `/queues/...` v2 address. |
| `demos/amqp10/publisher.py` | `proton.Message`, `create_sender()`, and synchronous broker settlement via `send()`. |
| `demos/amqp10/consumer.py` | `create_receiver(credit=1)`, `receive()`, explicit `accept()`/`reject()` outcomes. |
| `demos/amqp10/pika_publisher.py` | Optional cross-protocol producer using Pika and the default exchange. |
| `Dockerfile.amqp10` | Builds the Proton Python client in a separate Docker image. |

**Security note:** this demonstration intentionally uses username/password SASL PLAIN on the isolated Docker network, without TLS. Real deployments should use TLS (`amqps`), appropriate credentials, and least-privilege access.

Stop the Proton consumer independently when finished:

```bash
make -f Makefile.services amqp10-stop
```

---


---

## Appendix A — Start all AMQP 0-9-1 consumers at once

For a final walkthrough you can start RabbitMQ and all long-running consumer scenarios together:

```bash
make -f Makefile.services all
```

Then use the publisher Makefile from another terminal:

```bash
make -f Makefile.publishers work
make -f Makefile.publishers fanout
make -f Makefile.publishers direct
make -f Makefile.publishers topic
make -f Makefile.publishers headers
make -f Makefile.publishers rpc
make -f Makefile.publishers duplicate
make -f Makefile.publishers ordering
```

The redelivery scenario remains separate because it intentionally requires a consumer crash and restart. The AMQP 1.0 Proton consumer is also a separate target (`make -f Makefile.services amqp10`).

---

## Appendix B — Source map for a classroom walkthrough

If you want to open only a few files while presenting the lab, use this sequence:

| Concept | Publisher / client | Consumer / service | Key line of reasoning |
|---|---|---|---|
| Direct | `demos/direct/publisher.py` | `demos/direct/consumer.py` | exact routing-key / binding-key match |
| Topic | `demos/topic/publisher.py` | `demos/topic/consumer.py` | wildcard binding patterns |
| Headers | `demos/headers/publisher.py` | `demos/headers/consumer.py` | metadata-based routing with `x-match` |
| Work Queue | `demos/work_queue/publisher.py` | `demos/work_queue/worker.py` | same queue + competing consumers + ACK + prefetch |
| Fanout | `demos/fanout/publisher.py` | `demos/fanout/consumer.py` | one exchange, one queue per subscriber |
| Request/Reply | `demos/request_reply/client.py` | `demos/request_reply/server.py` | `reply_to` + `correlation_id` |
| Redelivery | `demos/reliability/redelivery_publisher.py` | `demos/reliability/redelivery_consumer.py` | crash before ACK -> broker redelivery |
| Idempotency | `demos/reliability/duplicate_publisher.py` | `demos/reliability/idempotent_consumer.py` | repeated `message_id` -> skip duplicate effect |
| Ordering | `demos/ordering/publisher.py` | `demos/ordering/consumer.py` | route the same key to the same processing path |
| AMQP 1.0 | `demos/amqp10/publisher.py` | `demos/amqp10/consumer.py` | Proton sender/receiver links, transfer settlement; optional Pika interop |

A useful teaching rule is to read **the topology first** (exchange, queue, binding), then the call to `basic_publish()`, and finally the consumer callback and its ACK behavior.

---

## Appendix C — RabbitMQ concepts mapped to this lab

| Concept | In this lab |
|---|---|
| Producer | one-shot Dockerized scripts in `Makefile.publishers` |
| Consumer | long-running Dockerized services in `Makefile.services` |
| Message | JSON body + AMQP properties/headers |
| Exchange | `orders.fanout`, `orders.direct`, `orders.topic`, `orders.headers`, ... |
| Binding | rules connecting exchanges to queues |
| Queue | durable buffers such as `orders.work` or `inventory.events` |
| ACK | sent manually after successful processing in reliability-sensitive demos |
| Routing key | used by direct/topic exchanges |
| Message headers | used by the headers exchange and message IDs |
| Prefetch | limits outstanding work in the work-queue example |

---

## Appendix D — Why the examples use JSON

AMQP transports bytes. RabbitMQ does not require JSON: the body could contain JSON, Protobuf, Avro, text, or another binary format.

The lab uses JSON because the focus is on **messaging topology and delivery semantics**, not serialization performance.

AMQP properties remain separate from the message body and are used for metadata such as:

```text
message_id
correlation_id
reply_to
content_type
custom headers
```

---

## Appendix E — Broker-based messaging and availability

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

This does not make failures disappear. RabbitMQ becomes infrastructure that must be operated reliably, and applications must handle delayed delivery, duplicate delivery, poison messages, back pressure, schema evolution, and observability.

---

## Appendix F — Useful classroom sequence

```text
Terminal 1: start consumers       Terminal 2: publish
          |                                 |
          +------------ observe ------------+
                        |
                        v
Direct / Topic / Headers
exchange routing policies
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
        |
        v
AMQP 1.0 (Proton)
same broker, new wire protocol
        |
        v
Pika -> Proton (optional)
cross-protocol interoperability
```

---

## Appendix G — Stop and clean up

Stop the complete lab while keeping persisted RabbitMQ and SQLite volumes:

```bash
make -f Makefile.services down
```

Remove containers **and all persisted demo state**:

```bash
make -f Makefile.services reset
```
