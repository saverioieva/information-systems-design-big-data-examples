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
- use **OpenAPI** as a REST contract and generate clients from it;
- understand synchronous REST-based RPI;
- use **gRPC** and **Protocol Buffers** for internal service-to-service communication;
- distinguish generated gRPC stubs/messages from application ports and domain objects;
- compare the four gRPC interaction models: unary, server streaming, client streaming, and bidirectional streaming;
- observe the difference between a public REST boundary and an internal gRPC boundary;
- use Docker-based tooling to keep the labs reproducible.

## Recommended sequence

| Step | Example | Main question |
|---|---|---|
| 1 | [`decomposition/`](decomposition/) | **Which services should exist?** |
| 2 | [`api-versioning/`](api-versioning/) | **How can a published API evolve without unnecessarily breaking clients?** |
| 3 | [`hexagonal-rpi-order-service/`](hexagonal-rpi-order-service/) | **How should one microservice be structured internally?** |
| 4 | [`grpc-order-service/`](grpc-order-service/) | **How can separate services communicate efficiently using gRPC?** |

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

### DTOs vs domain models

Pydantic is **not part of Hexagonal Architecture**.

Pydantic models belong to the REST boundary and are used for:

- HTTP request/response schemas;
- validation;
- serialization;
- FastAPI/OpenAPI integration.

They are transport DTOs, not domain entities.

```text
HTTP / JSON
    ↓
Pydantic DTO
    ↓
REST adapter
    ↓
OrderUseCases
    ↓
Application / Domain
```

The domain model remains independent from FastAPI and Pydantic.

### Docker-first workflow

The lab is designed so that the host machine only needs **Docker and Docker Compose**.

Application execution, client execution, client generation, and tests can run in containers.

Generated client code is written under:

```text
generated/
```

but that directory is intentionally excluded from Git because generated artifacts can always be recreated from the OpenAPI contract.

---

## 4. REST outside, gRPC inside

Directory:

```text
grpc-order-service/
```

This lab demonstrates communication between **two different services**:

```text
External Client
      |
      | REST / JSON
      v
Checkout Service
      |
      | gRPC / HTTP/2 / Protocol Buffers
      v
Inventory Service
```

The main scenario is intentionally realistic:

- the **Checkout Service** exposes a public REST API;
- the Checkout application core depends on an `InventoryGateway` outbound port;
- `GrpcInventoryClient` implements that port;
- the generated gRPC stub is used only inside the adapter;
- the **Inventory Service** exposes a gRPC server adapter;
- that adapter invokes `InventoryUseCases`;
- `InventoryApplicationService` implements the inbound port.

### Checkout side

```text
REST Adapter
    ↓
CheckoutUseCases
    ↑
CheckoutApplicationService
    ↓
InventoryGateway
    ↑
GrpcInventoryClient
    ↓
generated gRPC stub
```

### Inventory side

```text
gRPC request
    ↓
GrpcInventoryAdapter
    ↓
InventoryUseCases
    ↑
InventoryApplicationService
    ↓
InventoryRepository
    ↑
InMemoryInventoryRepository
```

The generated gRPC server interface is infrastructure code. It is **not** the application inbound port.

Likewise, the generated gRPC client stub is **not** the Checkout application's outbound port. The application port is `InventoryGateway`.

### Protocol Buffers and transport DTOs

Generated Protocol Buffer message classes play a role similar to Pydantic models at the REST boundary:

```text
Pydantic models       → REST transport DTOs
Protobuf messages     → gRPC transport DTOs
Domain objects/ports  → application and domain
```

Transport-specific objects should remain outside the application core.

### Four gRPC interaction models

The `InventoryService` contract demonstrates:

```text
Unary
Server Streaming
Client Streaming
Bidirectional Streaming
```

The public REST API is used mainly to demonstrate a realistic **REST → unary gRPC** collaboration.

The streaming interaction models are tested directly against the gRPC service rather than being artificially mapped to REST.

### Postman

Postman is useful for observing both boundaries of the lab:

```text
Postman HTTP
    ↓
Checkout REST API
    ↓
unary gRPC
    ↓
Inventory Service

Postman gRPC
    ↓
Inventory Service directly
```

For REST, Postman can import the OpenAPI document exposed by FastAPI or an explicit OpenAPI file.

For gRPC, Postman can use:

- `proto/inventory.proto`; or
- gRPC Server Reflection.

This allows the four gRPC interaction models to be exercised graphically.

### Inspecting gRPC traffic with Docker/TShark

The lab also includes an optional Docker-based TShark tool for inspecting traffic on port `50051` without installing Wireshark on the host.

Conceptually:

```text
Protocol Buffer message
        ↓
binary serialization
        ↓
gRPC message framing
        ↓
HTTP/2 DATA frames
```

The sniffer is a diagnostic/teaching tool only; it is not part of the application architecture.

### Persistence scope

The Inventory Service intentionally uses:

```text
InventoryRepository
        ↑
InMemoryInventoryRepository
```

There is therefore a real outbound port and a real concrete adapter, but **no external database** in this lab.

This is deliberate: persistence was already demonstrated in the Hexagonal Architecture lab, while this example focuses on gRPC contracts, service-to-service communication, generated code, and interaction models.

A production-oriented extension could replace the adapter with:

```text
InventoryRepository
        ↑
PostgresInventoryRepository
        ↓
PostgreSQL
```

without changing the application core.

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

Additional diagnostic tools are provided through containers when practical.

---

## Scope of the examples

These projects are teaching aids, not complete production systems.

They deliberately keep the domain small so that architectural decisions remain visible. Concerns such as authentication, authorization, observability, distributed tracing, retries, service discovery, production database migrations, and deployment orchestration can be introduced separately without obscuring the concepts demonstrated here.
