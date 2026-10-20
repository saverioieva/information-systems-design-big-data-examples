# Asynchronous Messaging with AMQP and RabbitMQ

This lab introduces **asynchronous communication between microservices** using RabbitMQ and the AMQP 0-9-1 messaging model.

The examples are intentionally small and deterministic. Their purpose is to make messaging topology and delivery semantics visible before introducing larger event-driven workflows.

All Python code runs in Docker containers. The host only needs Docker, Docker Compose, and `make` as a convenience wrapper.

---

## Learning goals

By the end of the lab you should be able to explain and observe:

- temporal decoupling between producers and consumers;
- message headers, payloads, channels, queues, and exchanges;
- point-to-point, publish/subscribe, and asynchronous request/reply interactions;
- why a message broker provides routing, buffering, and delivery;
- RabbitMQ direct, fanout, topic, and headers exchanges;
- competing consumers, prefetch, and manual acknowledgements;
- one queue per independent publish/subscribe subscriber;
- `reply_to` and `correlation_id` in request/reply messaging;
- redelivery, duplicate processing, and idempotent consumers;
- the relationship between concurrency and ordering;
- how AsyncAPI describes an event-driven contract.

---

## Lab roadmap - same order as the slides

The README deliberately follows the same progression used in the lecture slides.

| Step | Slide topic | Executable example |
|---|---|---|
| 1 | Asynchronous Messaging: Messages and Channels | concepts used by all demos |
| 2 | Asynchronous Interaction Styles | work queue, fanout, request/reply |
| 3 | Why Use a Message Broker? | RabbitMQ + Management UI |
| 4 | AMQP and RabbitMQ: Message Flow | broker inspection with queues/exchanges/bindings |
| 5 | AMQP Exchange Types | direct, fanout, topic, headers |
| 6 | Point-to-Point and Work Queues | competing workers, prefetch, ACK |
| 7 | Publish/Subscribe and Event Routing | one queue per subscriber + buffering demo |
| 8 | Request/Reply over RabbitMQ | `reply_to` + `correlation_id` |
| 9 | Reliability, Duplicates, and Ordering | redelivery, idempotency, ordering by key |
| 10 | AsyncAPI and Architectural Trade-offs | `asyncapi/order-events.yaml` |

This order is intentional: first understand the communication model, then RabbitMQ routing, then the higher-level interaction patterns and reliability concerns.

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

`demos/common.py` contains the RabbitMQ connection and JSON serialization helpers shared by the examples.

`docker-compose.yml` is the composition root for the lab: RabbitMQ and all scenario-specific consumers use the same Dockerized Python application image.

---

## Prerequisites and initial setup

Required on the host:

```text
Docker
Docker Compose
make
```

No local Python, Pika, RabbitMQ CLI, or AMQP tooling is required.

Build the shared image if you want to warm the Docker cache:

```bash
make build
```

The scenario targets also build the image when required, so the explicit build step is optional.

To completely remove containers, broker state, and the SQLite idempotency volume:

```bash
make reset
```

---

# 1. Asynchronous Messaging: Messages and Channels

In asynchronous messaging, a producer sends a message without requiring the consumer to process it immediately.

```text
Producer ---> Message Channel ---> Consumer
                |
                +-- message can wait here
```

This provides **temporal decoupling**: producer and consumer can progress at different speeds and do not necessarily need to be executing at the same instant.

A message has two conceptually different parts:

```text
Message
├── metadata / headers
│   ├── message_id
│   ├── correlation_id
│   ├── reply_to
│   ├── routing properties
│   └── custom headers
└── payload
    └── application data
```

In this lab the payload is JSON because the focus is messaging topology and delivery semantics. AMQP transports bytes, so other encodings such as Protobuf or Avro could also be used.

Two channel styles will appear repeatedly:

- **Point-to-point**: each message is processed by one consumer.
- **Publish/subscribe**: an event can be delivered to multiple interested subscribers.

The later examples make both styles concrete.

---

# 2. Asynchronous Interaction Styles

The slides introduce three interaction styles. The lab implements all three.

## Point-to-point

A producer sends a command or task to a queue. If several consumers compete on that queue, one consumer processes each message.

```text
Producer ---> Queue ---> Worker A
                  \\---> Worker B

one message -> one worker
```

Executable example:

```bash
make work-demo
```

## Publish/subscribe

A producer publishes an event to an exchange. RabbitMQ can route a copy to multiple queues, allowing each independent subscriber to process its own copy.

```text
Producer ---> Exchange ---> Queue A ---> Subscriber A
                     \\----> Queue B ---> Subscriber B
```

Executable example:

```bash
make fanout-demo
```

## Asynchronous request/reply

A request and a reply travel through different messaging paths. A correlation ID associates the reply with the original request.

```text
Client ---> Request Queue ---> Service
  ^                              |
  |                              v
  +--------- Reply Queue <-------+
           correlation_id
```

Executable example:

```bash
make rpc-demo
```

The transport remains asynchronous even if the client deliberately waits for the reply.

---

# 3. Why Use a Message Broker?

With direct communication, the sender must know how to reach the receiver and must directly handle receiver unavailability.

```text
Direct communication

Service A --------------------> Service B
                                must be reachable now
```

With broker-based messaging, RabbitMQ provides a stable intermediary for **routing, buffering, and delivery**.

```text
Broker-based communication

Service A ---> RabbitMQ ---> Service B
                 |
                 +-- can buffer messages
```

The producer does not need to know the network location of the consumer. If a queue remains available, messages can wait while a consumer is temporarily offline.

The trade-off is that the broker becomes shared infrastructure that must itself be monitored, scaled, and operated for high availability.

Start RabbitMQ:

```bash
make up
```

Show the Management UI URL and credentials:

```bash
make management
```

Management UI:

```text
http://localhost:15672
username: student
password: student
```

AMQP is exposed on port `5672`; the Management UI uses port `15672`.

---

# 4. AMQP and RabbitMQ: Message Flow

The central RabbitMQ flow is:

```text
Producer
   |
   | publish
   v
Exchange
   |
   | binding / routing rule
   v
Queue
   |
   | delivery
   v
Consumer
   |
   +---- ACK ----> RabbitMQ
```

The roles are different:

- **Producer** publishes a message.
- **Exchange** routes the message; it is not the application buffer.
- **Binding** connects an exchange to a queue and defines a routing rule.
- **Queue** buffers messages until they can be consumed.
- **Consumer** processes a delivery and can acknowledge it after successful processing.

If a consumer fails before acknowledging a message, RabbitMQ can make that message available for delivery again.

Queue durability, message persistence, and consumer acknowledgements solve different problems and should not be treated as synonyms.

Inspect the broker from the command line:

```bash
make queues
make exchanges
make bindings
```

The commands run `rabbitmqctl` inside the RabbitMQ container and use RabbitMQ's `pretty_table` formatter.

A blank `source_name` in `make bindings` is intentional. It represents RabbitMQ's **default exchange** (`""`). Every declared queue is automatically bound to the default exchange using the queue name as its routing key.

For example:

```text
source_name      destination_name       destination_kind   routing_key
                 orders.work           queue              orders.work
orders.direct    orders.failures       queue              order.failed
orders.fanout    inventory.events      queue              inventory.events
```

The first row means:

```text
source exchange = ""     (default exchange)
routing key     = orders.work
destination     = orders.work queue
```

---

# 5. AMQP Exchange Types

RabbitMQ exchanges define how published messages are routed to queues.

This lab demonstrates the four exchange types introduced in the slides.

## 5.1 Direct Exchange - exact routing keys

Run:

```bash
make direct-demo
```

The publisher sends:

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
              +----------> all-statuses <------+
                                               |
                                               +--> failures
```

A **direct exchange** routes a message to queues whose binding key exactly matches the message routing key.

Inspect the actual bindings:

```bash
make bindings
```

## 5.2 Fanout Exchange - broadcast to every bound queue

Run:

```bash
make fanout-demo
```

```text
                       orders.fanout
Order Service  ------> [ fanout exchange ]
                              |
                    +---------+---------+
                    |                   |
                    v                   v
            inventory.events   notification.events
```

A **fanout exchange** ignores the routing key and sends a copy of each message to every bound queue.

The important point is that the exchange creates the routing decision; the queues provide the independent buffers.

## 5.3 Topic Exchange - wildcard routing

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

For a topic exchange:

- `*` matches exactly one routing-key word;
- `#` matches zero or more routing-key words.

For example:

```text
order.eu.created
order.us.cancelled
```

could be matched with patterns such as:

```text
order.*.created
order.#
```

## 5.4 Headers Exchange - route using metadata

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

Consumers are configured as:

```text
eu-order-handler  -> type=order AND region=eu
payment-handler   -> type=payment
```

A **headers exchange** routes according to message header values instead of the routing key.

This is useful when routing depends on several metadata attributes rather than on one hierarchical routing-key string.

---

# 6. Point-to-Point and Work Queues

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

This is the **competing consumers** pattern:

- multiple workers consume from the same queue;
- each message is processed by one worker, not by every worker;
- adding workers can increase throughput.

The example also demonstrates flow control and reliable work processing:

- the queue is durable;
- messages are persistent;
- `prefetch_count=1` limits outstanding unacknowledged work assigned to each worker;
- a manual ACK is sent after processing.

Inspect the queue while workers are active:

```bash
make queues
```

Stop the workers:

```bash
make work-stop
```

## Ordering consequence

The queue has an ordered sequence of deliveries, but with several consumers the **completion order of the business work is not guaranteed**. Different workers may finish at different times.

This point is revisited in Step 9.

---

# 7. Publish/Subscribe and Event Routing

Publish/subscribe is not just "multiple consumers". Independent subscribers need **independent queues**.

```text
Order Service
     |
     v
orders.fanout
   /       \
  v         v
inventory  notification
.events     .events
   |           |
   v           v
Inventory   Notification
Service      Service
```

If Inventory Service and Notification Service shared the same queue, they would become competing consumers and each message would be processed by only one of them.

With one queue per subscriber, each service receives its own copy and can scale, fail, or evolve independently.

Start the two fanout subscribers:

```bash
make fanout-up
```

Publish an event with the regular demo if both subscribers are online:

```bash
make fanout-demo
```

## Observe broker buffering while one subscriber is offline

This experiment makes temporal decoupling visible.

Start the subscribers:

```bash
make fanout-up
```

Stop only the Notification subscriber:

```bash
docker compose stop fanout-notification
```

At this point:

```text
Inventory subscriber       RUNNING
Notification subscriber    STOPPED
```

Publish another event **without** invoking `make fanout-demo`, because that target also runs `fanout-up` and would start the stopped subscriber again:

```bash
docker compose --profile tools run --rm lab \
  python -m demos.fanout.publisher --order-id order-456
```

Inspect the queues:

```bash
make queues
```

Expected behavior:

```text
orders.fanout
   |
   +--> inventory.events
   |       |
   |       +--> active consumer -> process -> ACK
   |
   +--> notification.events
           |
           +--> consumer offline -> message remains queued
```

Restart only the Notification subscriber:

```bash
docker compose start fanout-notification
```

Inspect its logs:

```bash
docker compose logs --tail=30 fanout-notification
```

The subscriber should receive the message that RabbitMQ buffered while it was offline.

Inspect the queues again:

```bash
make queues
```

After processing and acknowledgement, the Notification queue should become empty again.

The key distinction is:

> **The exchange performs routing; the queue performs buffering.**

The demo uses named durable queues specifically so the queue remains present when its consumer is stopped.

Direct and topic exchanges can also implement event routing when only selected subscribers should receive an event; fanout is the simplest broadcast case.

---

# 8. Request/Reply over RabbitMQ

Run:

```bash
make rpc-demo
```

The flow is:

```text
Client
  |
  | request
  | reply_to = callback queue
  | correlation_id = X
  v
pricing.rpc
  |
  v
Pricing Service
  |
  | reply
  | correlation_id = X
  v
callback queue
  |
  v
Client matches reply X to request X
```

The client creates an exclusive callback queue and places its name in the `reply_to` property.

A unique `correlation_id` identifies the request. The service copies the same ID into the reply so the client can associate responses with requests.

The important distinction is:

> The transport remains asynchronous even if the client deliberately blocks while waiting for the reply.

Request/reply over messaging can therefore recreate synchronous-looking semantics on top of an asynchronous transport.

---

# 9. Reliability, Duplicates, and Ordering

Reliability in messaging is not one feature. Several mechanisms address different failure modes.

## 9.1 Manual ACK, failure, and redelivery

Run:

```bash
make redelivery-demo
```

The deterministic sequence is:

```text
1. publish one persistent message
2. consumer receives it
3. consumer crashes BEFORE ACK
4. RabbitMQ makes the unacknowledged message available again
5. a new consumer receives the same message
6. the second consumer ACKs it
```

The second delivery reports:

```text
redelivered=True
```

This shows why an application must be prepared for **at-least-once delivery**: the same business message may be processed more than once.

An ACK does not mean "exactly once" business execution. It tells RabbitMQ that this delivery has been successfully handled from the consumer's point of view.

## 9.2 Idempotent Consumer

Run:

```bash
make duplicate-demo
```

The publisher intentionally sends the same `message_id` twice and then sends a new message.

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
process  skip effect
  |       |
store ID  |
  +---+---+
      |
     ACK
```

This is the **Idempotent Consumer** pattern: duplicate delivery is acknowledged, but the protected business effect is applied only once.

In a production system, the processed-message record normally needs transaction semantics compatible with the business update it protects.

Reset the stored teaching state with:

```bash
make reset
```

## 9.3 Durability and persistence

The demos use durable queues and persistent messages where reliability across broker restarts matters.

Keep these concepts separate:

```text
manual ACK
    -> consumer-side delivery completion / possible redelivery

durable queue
    -> queue definition can survive broker restart

persistent message
    -> message is marked for durable storage

publisher confirm
    -> producer can learn that RabbitMQ accepted responsibility for a publish
```

The lecture also introduces **publisher confirms**. The current lab does not have a dedicated publisher-confirm demo; it focuses on consumer acknowledgements, redelivery, duplicates, and ordering. A publisher confirm is not a consumer ACK and does not mean that a consumer has processed the message.

## 9.4 Ordering with concurrent consumers

With several consumers, messages can complete out of order even if the queue delivered them in sequence.

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

The example does **not** claim global ordering across independently processed queues.

Instead, it demonstrates the strategy used in the slides:

> If ordering matters, route messages with the same key to the same ordered processing path.

For many systems, ordering per order, aggregate, customer, or another business key is more useful than one global order.

---

# 10. AsyncAPI and Architectural Trade-offs

Open:

```text
asyncapi/order-events.yaml
```

The file describes an event-driven contract using AsyncAPI 3.0 concepts.

```text
AsyncAPI document
├── servers
│   └── where applications connect
├── channels
│   └── communication paths
├── messages
│   └── headers and payload schemas
├── operations
│   └── send / receive behavior
└── protocol bindings
    └── protocol-specific details
```

A useful analogy is:

```text
REST                         Messaging
----                         ---------
OpenAPI                      AsyncAPI
HTTP endpoint                Channel
request/response schema      Message schema
HTTP operation               send/receive operation
```

The AsyncAPI file is deliberately independent from the Python handlers. It is a **contract**, not the implementation of a consumer.

## Architectural trade-offs

Asynchronous messaging can reduce direct temporal coupling:

```text
Synchronous collaboration
Service A ---> Service B
               must answer now

Asynchronous collaboration
Service A ---> RabbitMQ ---> Service B
                 |
                 +-- can buffer while B is temporarily offline
```

This improves some availability scenarios, but it does not make distributed-system complexity disappear.

Asynchronous systems introduce or make more visible concerns such as:

- eventual consistency;
- duplicate delivery and idempotency;
- ordering boundaries;
- backpressure and queue growth;
- schema evolution;
- poison messages and retry/dead-letter strategies;
- harder end-to-end tracing and observability;
- reliable operation of the broker itself.

The design goal is therefore not "use messaging everywhere". The goal is to choose asynchronous collaboration where temporal decoupling, buffering, independent scaling, or event distribution provide a concrete architectural advantage.

---

## Command summary

```bash
# Broker and inspection
make up
make management
make status
make queues
make exchanges
make bindings

# Exchange types
make direct-demo
make fanout-demo
make topic-demo
make headers-demo

# Point-to-point / work queues
make work-demo

# Publish/subscribe lifecycle
make fanout-up
docker compose stop fanout-notification
docker compose --profile tools run --rm lab \
  python -m demos.fanout.publisher --order-id order-456
make queues
docker compose start fanout-notification
docker compose logs --tail=30 fanout-notification

# Request/reply
make rpc-demo

# Reliability and ordering
make redelivery-demo
make duplicate-demo
make ordering-demo

# Cleanup
make down
make reset
```

---

## Mapping RabbitMQ concepts to the project

| RabbitMQ / messaging concept | In this lab |
|---|---|
| Producer | one-shot Dockerized publisher scripts |
| Message | JSON payload plus AMQP properties and headers |
| Exchange | `orders.fanout`, `orders.direct`, `orders.topic`, `orders.headers`, ... |
| Binding | routing rules connecting exchanges to queues |
| Queue | buffers such as `orders.work`, `inventory.events`, ... |
| Consumer | long-running Dockerized Python services |
| Consumer ACK | sent manually after successful processing in reliability-sensitive examples |
| Routing key | used by direct and topic exchanges |
| Message headers | used by headers exchange and reliability metadata |
| Prefetch | bounds outstanding work in the work-queue example |
| `reply_to` | identifies the reply destination in request/reply |
| `correlation_id` | matches a reply to its request |
| AsyncAPI | `asyncapi/order-events.yaml` |

---

## Suggested classroom sequence

If time is limited, run the examples in exactly this order:

```text
1. make up + make queues/exchanges/bindings
2. make direct-demo
3. make fanout-demo
4. make topic-demo
5. make headers-demo
6. make work-demo
7. fanout subscriber-offline buffering experiment
8. make rpc-demo
9. make redelivery-demo
10. make duplicate-demo
11. make ordering-demo
12. inspect asyncapi/order-events.yaml
```

This execution order mirrors the conceptual progression in the slides: **messages and channels -> interaction styles -> broker -> AMQP flow -> routing -> work queues -> publish/subscribe -> request/reply -> reliability -> contract and trade-offs**.
