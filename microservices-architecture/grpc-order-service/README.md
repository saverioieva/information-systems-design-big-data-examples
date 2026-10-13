# Microservices Architecture — Examples

This directory contains small, focused examples used in the **Microservices Architecture** part of the course.

The examples are intentionally separated by architectural concern. Each lab focuses on a specific design decision rather than trying to reproduce a complete production system.

## Learning objectives

After completing these examples, you should be able to:

- decompose a system into candidate microservices using **business capabilities** and **DDD subdomains**;
- distinguish **service decomposition** from the internal architecture of a service;
- evolve published REST contracts using **API versioning** and compatibility rules;
- structure a service using **Hexagonal Architecture**, with explicit inbound/outbound ports and adapters;
- distinguish **transport DTOs** from domain models;
- use **OpenAPI** as a REST contract and generate clients or a disposable server skeleton from it;
- understand synchronous REST-based RPI;
- use **gRPC** and **Protocol Buffers** for internal service-to-service communication;
- distinguish generated gRPC stubs/messages/service plumbing from application ports, adapters, and domain objects;
- compare the four gRPC interaction models: unary, server streaming, client streaming, and bidirectional streaming;
- observe the difference between a public REST boundary and internal REST/gRPC service-to-service boundaries;
- compare REST/JSON and gRPC/Protocol Buffers for the same Unary use case using Prometheus metrics;
- distinguish serialized application payload size from complete on-the-wire size;
- use Docker-based tooling to keep the labs reproducible.

## Recommended sequence

| Step | Example | Main question |
|---|---|---|
| 1 | [`decomposition/`](decomposition/) | **Which services should exist?** |
| 2 | [`api-versioning/`](api-versioning/) | **How can a published API evolve without unnecessarily breaking clients?** |
| 3 | [`hexagonal-rpi-order-service/`](hexagonal-rpi-order-service/) | **How should one microservice be structured internally?** |
| 4 | [`grpc-order-service/`](grpc-order-service/) | **How can separate services communicate through REST or gRPC, and how can the trade-offs be measured?** |

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
Service-to-service communication
```

---

## 1. Service decomposition

Directory:

```text
decomposition/
├── by-capability/
└── by-subdomain/
```

These examples focus only on **service boundaries**.

### By business capability

[`decomposition/by-capability/`](decomposition/by-capability/) groups services around what the business does.

Examples of questions:

- What are the main business capabilities?
- Which capabilities should become independently deployable services?
- Which team could own each capability end to end?

### By DDD subdomain

[`decomposition/by-subdomain/`](decomposition/by-subdomain/) focuses on differences in domain language, rules, and models.

Important distinctions:

```text
Subdomain       → problem-space concept
Bounded Context → model/language boundary
Microservice    → deployable software unit
```

A microservice may implement a bounded context, but the concepts are not identical.

> **Scope:** these examples focus on **service decomposition and boundary design**. They intentionally do not apply Hexagonal Architecture to the internal structure of each service. Ports and adapters are introduced separately in the [`hexagonal-rpi-order-service`](hexagonal-rpi-order-service/) example.

---

## 2. API versioning

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

Typical examples include:

```text
/v1/orders/{id}
/v2/orders/{id}
```

The main teaching point is:

> **API versioning is about compatibility at the boundary; Hexagonal Architecture is about dependency management inside the boundary.**

Conceptually:

```text
Client
   ↓
Published API contract
   ↓
API versioning
   ↓
REST adapter
   ↓
Application internals
```

> **Scope:** this example focuses on API contract evolution and compatibility. It intentionally does not model the internal service structure using Hexagonal Architecture.

---

## 3. Hexagonal Architecture + REST/OpenAPI

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
- optional Dockerized OpenAPI server-skeleton generation for inspection;
- Docker Compose.

### Core dependency structure

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

### Alternative REST adapters

The same application core can be exposed using different frameworks:

```text
FastAPI APIRouter
       ↓
OrderUseCases

Flask Blueprint
       ↓
OrderUseCases
```

Changing the web framework changes the **adapter**, not the application core.

### DTOs, Pydantic, and domain models

A **DTO (Data Transfer Object)** represents data crossing a boundary. It is shaped for communication, not for business behavior. In the REST adapter, request/response DTOs describe the JSON exchanged with clients; they are therefore different from domain entities.

**Pydantic** is a Python library for parsing, validation, and serialization based on type annotations. It is **not part of Hexagonal Architecture**. FastAPI integrates it directly, so Pydantic `BaseModel` classes naturally become REST DTOs and can drive request validation, response serialization, and generated OpenAPI schemas.

Flask, by contrast, does not require or automatically integrate Pydantic. In this lab the Flask adapter uses `request.get_json()`, plain dictionaries, explicit validation, and `jsonify()`. Pydantic could still be added to Flask, but it would be an explicit adapter choice.

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

For the FastAPI adapter, the REST DTOs are Pydantic models. For the Flask adapter, the same transport role is played by JSON dictionaries handled explicitly. In both cases, the domain model remains independent from FastAPI, Flask, and Pydantic.

### Docker-first workflow

The lab is designed so that the host machine only needs **Docker and Docker Compose**.

Application execution, client execution, client generation, and tests can run in containers.

Generated artifacts are written under:

```text
generated/
```

The lab can generate REST clients and, optionally, a FastAPI server skeleton from `order-api.yaml`. The server skeleton is used only to inspect what contract-first tooling can produce automatically; the running lab continues to use the handwritten Hexagonal adapters.

The directory is intentionally excluded from Git because these artifacts can always be recreated from the OpenAPI contract.

---

## 4. REST outside, REST/gRPC inside

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

### Inventory side: two inbound adapters, one core

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

This makes the Hexagonal Architecture idea concrete: replacing a transport adapter does not require changing the application core.

The REST adapter exposes only the availability operation needed for the Unary comparison. The gRPC contract still demonstrates all four interaction models:

```text
Unary
Server Streaming
Client Streaming
Bidirectional Streaming
```

### Protocol Buffers and transport DTOs

Generated Protocol Buffer messages and Pydantic models are both transport-level DTOs:

```text
Pydantic models       → REST transport DTOs
Protobuf messages     → gRPC transport DTOs
Domain objects/ports  → application and domain
```

The generated gRPC stub is transport plumbing, not the Checkout application's outbound port. The port is `InventoryGateway`.

The lab also includes an optional Dockerized code-generation profile that materializes `inventory_pb2.py` and `inventory_pb2_grpc.py` under `generated/` for inspection. This makes it possible to compare the generated `InventoryServiceServicer` with the handwritten `GrpcInventoryAdapter` and the framework-independent `InventoryUseCases` port without changing the runtime application.

```text
inventory.proto
      ↓
generated InventoryServiceServicer
      ↓
handwritten GrpcInventoryAdapter
      ↓
InventoryUseCases
      ↓
InventoryApplicationService
```

### Same use case, measurable protocol trade-offs

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

Prometheus collects metrics at the Checkout outbound-adapter boundary so that both protocols are observed from the same logical point. The lab compares:

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

These values do not include every transport byte. HTTP headers, the gRPC 5-byte message prefix, and HTTP/2 framing are separate concerns.

The intended lesson is **measure, do not assume**. On localhost and with tiny messages, latency differences can be noisy; the experiment is not designed to prove that gRPC is always faster.

### Postman

Postman can exercise all relevant boundaries:

```text
Postman HTTP
    → Checkout :8000 or :8001

Postman HTTP
    → Inventory REST :8081

Postman gRPC
    → Inventory gRPC :50051
```

For REST, Postman can import the OpenAPI documents exposed by FastAPI. For gRPC, it can use `proto/inventory.proto` or gRPC Server Reflection.

### Prometheus and Docker/TShark

Prometheus is included as a teaching collector for the REST-vs-gRPC comparison. An optional Dockerized TShark tool captures only the Inventory application-adapter ports: REST on `8081` and gRPC on `50051`. Prometheus `/metrics` traffic is intentionally outside that capture, so metric collection does not pollute the protocol comparison.

Conceptually:

```text
Prometheus
→ latency + serialized application payload metrics

TShark
→ REST/JSON traffic on :8081
→ gRPC/HTTP2 + binary Protobuf traffic on :50051
```

Both are diagnostic teaching tools, not application components.

### Persistence scope

Inventory intentionally uses:

```text
InventoryRepository
        ↑
InMemoryInventoryRepository
```

There is a real outbound port and a concrete adapter, but no external database. Persistence was already demonstrated in the Hexagonal Architecture lab, so this example keeps the focus on transport adapters, service-to-service contracts, gRPC interaction models, and measurable communication trade-offs.

---

## Cross-cutting design ideas

### Decomposition and Hexagonal Architecture are orthogonal

They solve different problems:

```text
Service decomposition
→ Which services should exist?

Hexagonal Architecture
→ How should one service be structured internally?
```

### Contracts and internals are different concerns

```text
OpenAPI / API versioning
→ external REST contract

gRPC / .proto
→ service-to-service contract

Ports
→ application-facing abstractions

Adapters
→ technology-specific implementations
```

### Generated transport code is not application architecture

Both contract technologies can produce useful framework/protocol scaffolding:

| Contract | Generated artifact to inspect | Handwritten architectural element |
|---|---|---|
| `order-api.yaml` | FastAPI server/controller skeleton | REST inbound adapter calling `OrderUseCases` |
| `inventory.proto` | `InventoryServiceServicer`, stub, message classes | `GrpcInventoryAdapter` calling `InventoryUseCases` |

The generator knows the transport contract. It does **not** decide the application's ports, domain model, use cases, repository abstractions, or dependency direction.

### Framework objects are adapter details

Examples:

```text
FastAPI APIRouter
Flask Blueprint
Pydantic BaseModel
gRPC generated stub
Protobuf generated message
SQLAlchemy mapping
```

None of these should define the application core.

---

## Tooling philosophy

The runnable labs are **Docker-first** whenever possible.

The goal is to avoid requiring students to install language-specific toolchains just to execute an example.

Typical host requirements are therefore limited to:

```text
Docker
Docker Compose
Postman        optional graphical client
```

Additional diagnostic and code-generation tools are provided through optional Compose profiles when practical. The normal runtime is unchanged when those profiles are not selected.

For the two contract-first code-generation demonstrations:

```text
hexagonal-rpi-order-service/  -> make generate-server-skeleton
grpc-order-service/           -> make generate-grpc-skeleton
```

Both commands write only to Git-ignored `generated/` directories and are optional inspection steps.

---

## Scope of the examples

These projects are teaching aids, not complete production systems.

They deliberately keep the domain small so that architectural decisions remain visible. Concerns such as authentication, authorization, distributed tracing, centralized logging, retries, service discovery, production database migrations, and deployment orchestration can be introduced separately without obscuring the concepts demonstrated here.
