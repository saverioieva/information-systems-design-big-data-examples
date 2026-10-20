# Microservices Architecture — Examples

This directory contains small, focused examples used in the **Microservices Architecture** part of the course.

The examples are intentionally separated by architectural concern. Each lab focuses on a specific design decision rather than trying to reproduce a complete production system.

## Learning objectives

After completing these examples, you should be able to:

- decompose a system into candidate microservices using **business capabilities** and **DDD subdomains**;
- distinguish **service decomposition** from the internal architecture of a service;
- evolve published REST contracts using **API versioning**, compatibility rules, URI versioning, and `Accept`-based media-type versioning;
- structure a service using **Hexagonal Architecture**, with explicit inbound/outbound ports and adapters;
- distinguish **transport DTOs** from domain models;
- use **OpenAPI** as a REST contract and generate clients or a disposable server skeleton from it;
- understand synchronous REST-based Remote Procedure Invocation (RPI);
- use **gRPC** and **Protocol Buffers** for internal service-to-service communication;
- distinguish generated gRPC stubs/messages/service plumbing from application ports, adapters, and domain objects;
- compare the four gRPC interaction models: unary, server streaming, client streaming, and bidirectional streaming;
- compare REST/JSON and gRPC/Protocol Buffers for the same Unary use case using Prometheus metrics and packet inspection;
- distinguish serialized application payload size from complete on-the-wire size;
- apply **timeouts, retries, circuit breakers, bulkheads, and graceful degradation** to synchronous RPI calls;
- distinguish **application-level** from **platform-provided service discovery**, including self/third-party registration and client/server-side discovery;
- explain **temporal decoupling** and the main asynchronous interaction styles;
- distinguish an AMQP **exchange**, **binding**, and **queue**;
- use RabbitMQ **direct, fanout, topic, and headers exchanges**;
- observe **competing consumers**, **prefetch**, **manual acknowledgements**, **redelivery**, and broker buffering;
- implement asynchronous **request/reply** using `reply_to` and `correlation_id`;
- explain why at-least-once processing requires **idempotent consumers**;
- reason about **message ordering** when multiple consumers process messages concurrently;
- use **AsyncAPI** to describe an event-driven contract;
- use Docker-based tooling to keep all labs reproducible.

---

## Recommended sequence

The examples follow the same conceptual progression used in the course slides.

| Step | Example | Main question |
|---|---|---|
| 1 | [`decomposition/`](decomposition/) | **Which services should exist?** |
| 2 | [`api-versioning/`](api-versioning/) | **How can a published API evolve without unnecessarily breaking clients?** |
| 3 | [`hexagonal-rpi-order-service/`](hexagonal-rpi-order-service/) | **How should one microservice be structured internally?** |
| 4 | [`grpc-order-service/`](grpc-order-service/) | **How can separate services communicate through REST or gRPC, and how can the trade-offs be measured?** |
| 5 | [`resilience-patterns/`](resilience-patterns/) | **How can synchronous service-to-service calls tolerate partial failures and resource exhaustion?** |
| 6 | [`service-discovery/`](service-discovery/) | **How are dynamic service instances registered, located, and selected at runtime?** |
| 7 | [`asynchronous-messaging-rabbitmq/`](asynchronous-messaging-rabbitmq/) | **How can services communicate asynchronously through a broker, and what delivery semantics must consumers handle?** |

The progression is deliberately:

```text
Business requirements
        ↓
Service decomposition
        ↓
Published API contracts
        ↓
Internal service architecture
        ↓
Synchronous service-to-service communication
        ↓
Resilience under partial failure
        ↓
Dynamic service discovery
        ↓
Asynchronous messaging and event-driven contracts
```

---

# 1. Service decomposition

Directory:

```text
decomposition/
├── by-capability/
└── by-subdomain/
```

These examples focus only on **service boundaries**.

## By business capability

[`decomposition/by-capability/`](decomposition/by-capability/) groups services around what the business does.

Typical questions are:

- What are the main business capabilities?
- Which capabilities should become independently deployable services?
- Which team could own each capability end to end?

## By DDD subdomain

[`decomposition/by-subdomain/`](decomposition/by-subdomain/) focuses on differences in domain language, rules, and models.

Important distinctions:

```text
Subdomain       → problem-space concept
Bounded Context → model/language boundary
Microservice    → deployable software unit
```

A microservice may implement a bounded context, but the concepts are not identical.

> **Scope:** these examples focus on **service decomposition and boundary design**. They intentionally do not apply Hexagonal Architecture to the internal structure of each service. Ports and adapters are introduced separately in the [`hexagonal-rpi-order-service/`](hexagonal-rpi-order-service/) lab.

---

# 2. API versioning

Directory:

```text
api-versioning/
```

This lab focuses on the evolution of a **published REST contract**.

It demonstrates the distinction between:

```text
backward-compatible change
        vs
breaking API change
```

and shows how multiple major API versions can coexist when necessary.

Two ways to expose major versions are compared:

```text
URI versioning
/v1/orders/{id}
/v2/orders/{id}

Media-type versioning
/orders/{id}
Accept: application/vnd.ftgo.order.v1+json
Accept: application/vnd.ftgo.order.v2+json
```

The media-type variant keeps the resource URI stable and uses HTTP content negotiation. Responses use `Vary: Accept` so caches can distinguish representations.

The lab also separates two concepts that are often confused:

```text
Software release version
1.0.0 → 1.1.0 → 1.1.1

Published API major version
v1 → v2 only when the contract becomes incompatible
```

The main teaching point is:

> **API versioning is about compatibility at the boundary; Hexagonal Architecture is about dependency management inside the boundary.**

> **Scope:** this example focuses on API contract evolution and compatibility. It intentionally does not model the internal service structure using Hexagonal Architecture.

---

# 3. Hexagonal Architecture + REST/OpenAPI

Directory:

```text
hexagonal-rpi-order-service/
```

This lab implements a small **Order Service** and connects several concepts:

- Hexagonal Architecture;
- explicit inbound and outbound ports;
- REST as synchronous RPI;
- FastAPI and Flask as alternative inbound adapters;
- PostgreSQL as an outbound persistence adapter;
- OpenAPI as the published contract;
- Swagger UI;
- generated REST clients;
- Dockerized OpenAPI code generation;
- Docker Compose.

## Core dependency structure

```text
FastAPI adapter ─┐
                 ├──> OrderUseCases <── OrderApplicationService
Flask adapter ───┘                         |
                                           v
                                    OrderRepository
                                           ^
                                           |
                               PostgresOrderRepository
```

The important dependency direction is **outside → inside**:

- the REST adapter invokes the `OrderUseCases` inbound port;
- `OrderApplicationService` implements the inbound port;
- the application core depends on the `OrderRepository` outbound port;
- `PostgresOrderRepository` implements the outbound port;
- framework and persistence details remain outside the core.

## Alternative REST adapters

The same application core can be exposed using different frameworks:

```text
FastAPI APIRouter
       ↓
OrderUseCases

Flask Blueprint
       ↓
OrderUseCases
```

The two containers represent **alternative deployments of the same logical Order Service**. They exist to demonstrate that different inbound adapters can reuse the same core; they are not two distinct business microservices.

Changing the web framework changes the **adapter**, not the application core.

## DTOs, Pydantic, and domain models

A **DTO (Data Transfer Object)** represents data crossing a boundary. It is shaped for communication, not for business behavior.

For the FastAPI adapter, REST DTOs are Pydantic models. For the Flask adapter, the same transport role is played by JSON dictionaries handled explicitly. In both cases, the domain model remains independent from FastAPI, Flask, and Pydantic.

```text
HTTP / JSON
    ↓
REST DTO / transport data
    ↓
REST adapter
    ↓
OrderUseCases
    ↓
Application / Domain
```

## Contract-first code generation

Generated artifacts are written under:

```text
generated/
```

and are intentionally excluded from Git because they can be recreated from the OpenAPI contract.

The lab first uses OpenAPI to generate clients. In the final code-generation step it can also generate a FastAPI server skeleton and connect the generated transport plumbing to the same handwritten application core.

Conceptually:

```text
order-api.yaml
      ↓
OpenAPI Generator
      ↓
generated server transport skeleton
      ↓
handwritten integration adapter
      ↓
OrderUseCases
      ↓
OrderApplicationService
```

The generated code remains **disposable transport scaffolding**. Business logic, ports, domain objects, and repository abstractions remain outside `generated/`.

> **Key lesson:** OpenAPI Generator can generate transport plumbing; it does not generate the Hexagonal Architecture of the application.

---

# 4. REST outside, REST/gRPC inside

Directory:

```text
grpc-order-service/
```

This lab demonstrates communication between **two different services** while keeping the internal transport replaceable behind Hexagonal Architecture ports.

The public boundary remains REST in both variants:

```text
External Client
      |
      | REST / JSON
      v
Checkout Service
      |
      +---- gRPC / HTTP/2 / Protocol Buffers ----> Inventory Service
      |
      +---- REST / HTTP / JSON -------------------> Inventory Service
```

Two deployments of the same Checkout code are used only to make the comparison explicit:

```text
:8000  Checkout + GrpcInventoryClient
:8001  Checkout + RestInventoryClient
```

Both implement the same application-owned outbound port:

```text
CheckoutApplicationService
          |
          v
    InventoryGateway
        ^          ^
        |          |
GrpcInventoryClient   RestInventoryClient
```

The Checkout application core therefore does not depend on either transport.

## Inventory side: two inbound adapters, one core

Inventory exposes the same `InventoryUseCases` through two inbound adapters:

```text
GrpcInventoryAdapter ----+
                         |
                         v
                  InventoryUseCases
                         ^
                         |
RestInventoryAdapter ----+
                         |
                         v
               InventoryApplicationService
                         |
                         v
                  InventoryRepository
                         ^
                         |
               InMemoryInventoryRepository
```

The REST adapter exposes the availability operation needed for the Unary comparison. The gRPC contract demonstrates all four interaction models:

```text
Unary
Server Streaming
Client Streaming
Bidirectional Streaming
```

## Protocol Buffers and transport DTOs

Generated Protocol Buffer messages and Pydantic models are both transport-level DTOs:

```text
Pydantic models        → REST transport DTOs
Protobuf messages      → gRPC transport DTOs
Domain objects / ports → application and domain
```

The generated gRPC stub is transport plumbing, not the Checkout application's outbound port. The application-owned port is `InventoryGateway`.

An optional Dockerized code-generation profile materializes generated gRPC code under `generated/` for inspection without changing the runtime application.

## Same use case, measurable protocol trade-offs

The lab sends the same public request through two paths:

```text
POST :8000/checkouts
    → Checkout core
    → GrpcInventoryClient
    → gRPC
    → GrpcInventoryAdapter
    → Inventory core

POST :8001/checkouts
    → Checkout core
    → RestInventoryClient
    → REST
    → RestInventoryAdapter
    → Inventory core
```

Prometheus collects metrics at the Checkout outbound-adapter boundary so that both protocols are observed from the same logical point.

The comparison includes:

- client-observed Inventory-call latency;
- serialized request payload size;
- serialized response payload size;
- request counts and outcomes.

For payload size, the experiment intentionally compares:

```text
JSON serialized application payload
vs
Protocol Buffer serialized application payload
```

These values do **not** include every transport byte. HTTP headers, gRPC framing, HTTP/2 framing, and lower-layer protocol overhead are separate concerns.

The intended lesson is **measure, do not assume**. On localhost and with small messages, latency differences can be noisy; the experiment is not designed to prove that gRPC is always faster.

## Prometheus and Docker/TShark

Prometheus is a teaching collector for application-level metrics. An optional Dockerized TShark tool exposes the lower-level network view of REST/JSON and gRPC/HTTP2/Protobuf traffic.

```text
Prometheus
→ latency + serialized application payload metrics

TShark
→ packets / frames / HTTP traffic
→ gRPC / HTTP2 + Protobuf traffic
```

The two views are complementary: Prometheus observations are not network-packet counts.

---

# 5. Resilience patterns for synchronous RPI

Directory:

```text
resilience-patterns/
```

This lab combines **Hexagonal Architecture** with a real API Composition Gateway and four downstream REST APIs:

```text
Order Service
Kitchen Service
Delivery Service
Payment Service
```

The gateway application core depends only on outbound ports:

```text
OrderCompositionService
      |
      +--> OrderGateway
      +--> KitchenGateway
      +--> DeliveryGateway
      +--> PaymentGateway
      +--> PaymentCache
```

Concrete HTTP adapters implement those ports and apply the technical resilience mechanisms around remote calls.

The effective call path is:

```text
HTTP outbound adapter
        ↓
per-service Bulkhead
        ↓
Circuit Breaker
        ↓
Retry policy
        ↓
HTTP timeout per attempt
        ↓
real downstream REST API
```

The responsibilities remain separate:

- **Timeout** bounds how long one remote attempt may wait;
- **Retry** handles selected transient failures with a bounded number of attempts and backoff;
- **Circuit Breaker** stops forwarding calls when failures become persistent and later probes recovery;
- **Bulkhead** bounds concurrency/queue capacity per dependency so one slow service does not consume all shared resources;
- **graceful degradation** is an application policy: optional data may be omitted or served from the Payment cache.

The application core does not depend on `httpx`, Tenacity, PyBreaker, semaphores, or thread-pool implementation details.

## Fault injection and diagnostics

The downstream services expose teaching-only administration endpoints that can inject failures and delays, for example:

```text
POST /admin/fail-next/{count}
POST /admin/delay/{milliseconds}
POST /admin/reset
```

These endpoints provide a simplified **controlled fault-injection mechanism inspired by Chaos Engineering**. They are used to reproduce transient failures, persistent outages, slow dependencies, retries, breaker transitions, and overload conditions without editing code.

Diagnostic endpoints let students exercise one dependency at a time through the same application ports and outbound adapters used by the normal gateway flow.

## Bulkhead isolation demo

`make bulkhead-demo` runs a reproducible experiment that slows Kitchen and sends enough concurrent requests to saturate only the Kitchen bulkhead.

The expected behavior is:

```text
Kitchen
→ some calls admitted
→ excess calls rejected quickly

Order / Delivery / Payment
→ remain responsive
```

The demo shows the core bulkhead idea: **saturation of one dependency is contained inside its own execution compartment**.

---

# 6. Service discovery

Directory:

```text
service-discovery/
```

This lab shows how clients avoid hardcoded instance addresses when service instances are created, removed, restarted, or relocated dynamically.

It uses the same logical `order-service` with three running instances and compares the two discovery patterns from the course slides.

## Application-level discovery

```text
Order instances
      |
      | self-register
      v
    Consul
      ^
      | query catalog
      |
Python Client
      |
      | selects one instance
      v
Order Service instance
```

Each Order Service instance registers its own address and health-check endpoint. The client queries Consul, receives the healthy instances, performs client-side selection/load balancing, and sends the request directly to the selected instance.

Typical flow:

```bash
make application-up
make application-demo
make application-stop-instance
make application-demo
make application-start-instance
make application-demo
```

The `application-demo` target is intentionally **observational**: it sends traffic through the currently available topology and does not recreate stopped service instances.

## Platform-provided discovery

```text
Order instances
      |
      | observed by
      v
Third-party Registrar
      |
      | register / deregister
      v
    Consul
      |
      | DNS
      v
Nginx / Platform Router
      |
      | direct request
      v
selected Order instance
```

The Order Service contains no registration logic. A dedicated registrar observes Docker containers and updates Consul, while Nginx resolves the logical service name through Consul DNS and performs server-side load balancing.

The client knows only one stable endpoint and never needs individual instance addresses.

Typical flow:

```bash
make platform-up
make platform-demo
make platform-stop-instance
make platform-demo
make platform-start-instance
make platform-demo
```

Again, `platform-demo` only generates traffic; it does not change the deployment topology.

> **Scope:** service discovery and Hexagonal Architecture are separate concerns. This lab focuses on where registration, lookup, instance selection, and routing responsibilities live.

---

# 7. Asynchronous Messaging with AMQP and RabbitMQ

Directory:

```text
asynchronous-messaging-rabbitmq/
```

This lab follows the asynchronous-messaging section of the course slides in the same conceptual order. It uses RabbitMQ and the AMQP 0-9-1 messaging model.

All Python code runs inside containers. The host needs only Docker and Docker Compose.

## 7.1 Messages, channels, and temporal decoupling

The first idea is that a producer can send a message without requiring the consumer to process it immediately.

```text
Producer
   |
   | message
   v
Channel / Broker
   |
   | later
   v
Consumer
```

A message contains:

- **headers / properties** for metadata such as identifiers, routing information, `reply_to`, or `correlation_id`;
- a **payload/body** containing the application data.

The lab distinguishes two basic channel semantics:

```text
Point-to-point
→ one message is processed by one consumer

Publish/subscribe
→ an event is copied to multiple independent subscriber queues
```

## 7.2 Asynchronous interaction styles

The lab then demonstrates the three interaction styles introduced in the slides:

```text
Point-to-point command
Publish/subscribe event
Asynchronous request/reply
```

The important distinction is that the **transport can remain asynchronous even when a client deliberately waits for a reply**.

## 7.3 Why use a message broker?

RabbitMQ acts as a stable intermediary between producers and consumers.

```text
Direct communication
Producer ------------------------> Consumer
                requires availability/location knowledge

Broker-based communication
Producer ----> RabbitMQ ----> Consumer
                  |
                  +-- routing
                  +-- buffering
                  +-- delivery
```

The broker provides **temporal decoupling**: a message can remain buffered while a consumer is temporarily offline.

The trade-off is that the broker itself becomes shared infrastructure that must be monitored, sized, and made highly available in production.

## 7.4 AMQP and RabbitMQ message flow

The core RabbitMQ flow is:

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

The roles are intentionally distinct:

- the **exchange routes** messages;
- the **binding** connects an exchange to a queue and defines the routing rule;
- the **queue buffers** messages;
- the **consumer processes** them;
- a manual **acknowledgement** tells RabbitMQ that processing completed successfully.

If a consumer fails before acknowledging a message, RabbitMQ can deliver it again.

Durable queues, persistent messages, acknowledgements, and publisher confirms solve related but different reliability problems.

Useful broker-side inspection commands are wrapped by the Makefile:

```bash
make queues
make exchanges
make bindings
```

The commands execute RabbitMQ CLI tools inside the broker container and use the built-in `pretty_table` formatter.

A blank `source_name` in `make bindings` represents RabbitMQ's **default exchange** (`""`). Each declared queue is automatically bound to that exchange using the queue name as its routing key.

## 7.5 AMQP exchange types

The lab demonstrates all four exchange types discussed in the slides.

### Direct exchange

Exact routing-key matching:

```text
order.created ---> matching binding ---> queue
order.failed  ---> matching binding ---> queue
```

Run:

```bash
make direct-demo
```

### Fanout exchange

The routing key is ignored and every bound queue receives a copy:

```text
                   orders.fanout
                        |
              +---------+---------+
              |                   |
              v                   v
      inventory.events    notification.events
```

Run:

```bash
make fanout-demo
```

### Topic exchange

Bindings use routing-key patterns with `*` and `#` wildcards.

Run:

```bash
make topic-demo
```

### Headers exchange

Routing is based on message headers rather than the routing key.

Run:

```bash
make headers-demo
```

## 7.6 Point-to-point processing and Work Queues

The Work Queue scenario uses multiple workers consuming from the same queue:

```text
Producer
   |
   v
orders.work
   |
   +------> Worker A
   |
   +------> Worker B
```

Each message goes to **one** worker, not to all workers.

The example demonstrates:

- competing consumers;
- manual acknowledgements;
- persistent messages;
- durable queue;
- `prefetch_count=1` as a simple form of consumer-side flow control.

Run:

```bash
make work-demo
```

## 7.7 Publish/Subscribe and event routing

The fanout scenario models an FTGO-style domain event:

```text
Order Service
      |
      | Order Created
      v
orders.fanout
   /         \
  v           v
inventory   notification
.events      .events
  |             |
  v             v
Inventory   Notification
Service      Service
```

Publish/subscribe requires **one queue per independent subscriber**. If two services shared one queue, they would become competing consumers instead of both receiving the event.

The demo deliberately uses named durable queues so broker buffering is visible.

A useful experiment is:

```bash
make fanout-up

docker compose stop fanout-notification

docker compose --profile tools run --rm lab \
  python -m demos.fanout.publisher --order-id order-456

make queues

docker compose start fanout-notification

docker compose logs --tail=30 fanout-notification

make queues
```

While Notification Service is stopped, its copy remains in `notification.events`. After the consumer restarts, RabbitMQ delivers the buffered event and the queue becomes empty after acknowledgement.

> **The exchange performs routing; the queue performs buffering.**

## 7.8 Request/Reply over RabbitMQ

The Request/Reply scenario recreates request/response semantics over asynchronous transport.

```text
Client
  |
  | request + reply_to + correlation_id
  v
Request Queue
  |
  v
Service
  |
  | reply + same correlation_id
  v
Reply Queue
  |
  v
Client
```

`reply_to` tells the server where to send the response. `correlation_id` lets the client match a reply with its original request.

Run:

```bash
make rpc-demo
```

## 7.9 Reliability, duplicates, and ordering

### Redelivery

With manual acknowledgements, a consumer that fails before sending the ACK can cause the same message to be delivered again.

Run:

```bash
make redelivery-demo
```

This is why messaging code must be designed for **at-least-once processing** rather than assuming exactly-once business execution.

### Idempotent consumer

The duplicate-handling scenario records processed message IDs and avoids applying the same business effect twice.

Run:

```bash
make duplicate-demo
```

Conceptually:

```text
message ID
    |
    v
already processed?
  /        \
 no        yes
 |          |
apply      skip
once
```

### Ordering

A queue has an order, but multiple concurrent consumers can complete work in a different order.

When per-entity ordering matters, related messages can be routed by a stable key such as `orderId` so that the same key reaches the same queue/consumer path.

Run:

```bash
make ordering-demo
```

## 7.10 AsyncAPI and architectural trade-offs

The lab contains:

```text
asyncapi/order-events.yaml
```

AsyncAPI plays a role for event-driven interfaces similar to OpenAPI for REST interfaces. It can make explicit:

- servers;
- channels;
- messages;
- operations;
- schemas;
- protocol bindings.

The final teaching point is that asynchronous messaging improves **temporal decoupling** and can reduce the requirement that all collaborating services be online at the same instant, but it introduces new concerns:

```text
Eventual consistency
Duplicate delivery
Idempotency
Ordering
Backpressure
Tracing across asynchronous flows
Broker operations
```

---

# Cross-cutting design ideas

## Decomposition and Hexagonal Architecture are orthogonal

They solve different problems:

```text
Service decomposition
→ Which services should exist?

Hexagonal Architecture
→ How should one service be structured internally?
```

## Contracts and internals are different concerns

```text
OpenAPI / API versioning
→ external REST contract

gRPC / .proto
→ synchronous service-to-service contract

AsyncAPI
→ asynchronous/event-driven contract

Ports
→ application-facing abstractions

Adapters
→ technology-specific implementations
```

## Generated transport code is not application architecture

Contract technologies can generate useful framework/protocol scaffolding:

| Contract | Generated artifact | Handwritten architectural element |
|---|---|---|
| `order-api.yaml` | REST client/server transport code | inbound adapter + `OrderUseCases` |
| `inventory.proto` | gRPC stub, servicer base, message classes | `GrpcInventoryAdapter` + `InventoryUseCases` |
| `order-events.yaml` | documentation/codegen input for event-driven interfaces | producer/consumer application logic and ports |

A generator knows the transport contract. It does **not** decide the application's domain model, use cases, repository abstractions, or dependency direction.

## Framework and protocol objects are adapter details

Examples:

```text
FastAPI APIRouter
Flask Blueprint
Pydantic BaseModel
gRPC generated stub
Protobuf generated message
RabbitMQ connection/channel
AMQP delivery properties
SQLAlchemy mapping
```

None of these should define the application core.

## Synchronous and asynchronous communication solve different problems

```text
Synchronous RPI
caller waits for a response
→ simple interaction model
→ latency and partial failures are immediately coupled

Asynchronous messaging
producer publishes a message
→ temporal decoupling
→ broker can buffer work/events
→ eventual consistency and delivery semantics must be handled
```

Neither style is universally better. The architecture should choose the interaction style that matches the business operation and consistency requirements.

---

# Tooling philosophy

The runnable labs are **Docker-first** whenever possible.

The goal is to avoid requiring students to install language-specific toolchains just to execute an example.

Typical host requirements are therefore limited to:

```text
Docker
Docker Compose
Postman        optional graphical client
```

Additional diagnostic and code-generation tools are provided through optional Compose profiles when practical.

Examples include:

```text
OpenAPI Generator
Protocol Buffer / gRPC code generation
Prometheus
TShark
RabbitMQ CLI
RabbitMQ Management UI
Consul UI
```

Generated code is placed under Git-ignored `generated/` directories whenever possible so that it can be deleted and reproduced from the corresponding contract.

---

# Scope of the examples

These projects are teaching aids, not complete production systems.

They deliberately keep the domain small so that architectural decisions remain visible.

Concerns such as authentication, authorization, distributed tracing, centralized logging, production database migrations, broker clustering, advanced schema-registry strategies, and production deployment orchestration can be introduced separately without obscuring the concepts demonstrated here.

The labs should therefore be read as a sequence of **focused architectural experiments**:

```text
service boundaries
    ↓
API compatibility
    ↓
ports and adapters
    ↓
synchronous transports
    ↓
resilience
    ↓
discovery
    ↓
asynchronous messaging
```
