# Microservices Architecture — Examples

This directory contains the runnable examples for the **Microservices Architecture** block.

The examples are intentionally small and focus on architectural decisions rather than production concerns. They currently cover three complementary topics:

- defining **service boundaries** through decomposition;
- evolving published **API contracts** without breaking consumers;
- implementing a service with **Hexagonal Architecture**, synchronous REST RPI, OpenAPI/Swagger tooling, and PostgreSQL.

## Learning objectives

After completing this block, students should be able to:

- explain why service boundaries should be driven by the business domain rather than technical layers;
- distinguish a business capability from a DDD subdomain / bounded context;
- derive candidate microservices from the same functional requirements using different decomposition strategies;
- explain how business-capability and DDD views can reinforce or refine each other;
- distinguish compatible API evolution from breaking contract changes;
- apply semantic versioning to an API contract;
- explain why API compatibility matters when old and new service implementations coexist during deployment;
- identify inbound/outbound ports and adapters in a concrete service implementation;
- trace a synchronous REST request from a FastAPI adapter through the application core to a PostgreSQL adapter;
- use an OpenAPI contract with Swagger UI and Swagger Codegen.

## Examples and recommended sequence

| Step | Example | Main idea |
|---:|---|---|
| 1 | [`decomposition/`](decomposition/) | Compare decomposition by business capability with decomposition by subdomain using the same FTGO supplier-management scenario |
| 2 | [`api-versioning/`](api-versioning/) | Evolve an FTGO Order API, keep v1 and v2 available together, and relate contract compatibility to rolling and blue-green deployments |
| 3 | [`hexagonal-rpi-order-service/`](hexagonal-rpi-order-service/) | Implement an Order Service with Hexagonal Architecture, synchronous REST RPI, FastAPI, PostgreSQL, OpenAPI, Swagger UI, and Swagger Codegen |

## Requirements

- Docker Engine 24 or newer
- Docker Compose v2
- `curl`
- Python 3 for the small API-versioning client scripts

Verify Docker:

```bash
docker --version
docker compose version
```

## 1. Service decomposition

Start from:

```bash
cd microservices-architecture/decomposition
```

Read [`scenario.md`](decomposition/scenario.md) first, then run the two implementations separately:

```bash
cd by-capability
# follow README.md
```

and:

```bash
cd ../by-subdomain
# follow README.md
```

The same FTGO requirements are intentionally implemented with different service-boundary decisions so that the reasoning can be compared directly.

## 2. API versioning

Start from:

```bash
cd microservices-architecture/api-versioning
```

Then follow [`api-versioning/README.md`](api-versioning/README.md).

The lab exposes an FTGO Order API through an API Gateway:

```text
/v1/orders/{id}  -> Order API 1.1.0
/v2/orders/{id}  -> Order API 2.0.0
```

It demonstrates a backward-compatible minor evolution, a breaking major evolution, and the effect of both contracts on old and new consumers.

The README also connects API compatibility with the existing **rolling** and **blue-green** deployment examples in `cloud-native-examples/`.

## 3. Hexagonal Order Service and synchronous REST RPI

Start from:

```bash
cd microservices-architecture/hexagonal-rpi-order-service
```

Then follow [`hexagonal-rpi-order-service/README.md`](hexagonal-rpi-order-service/README.md).

This lab follows one request end-to-end:

```text
OpenAPI contract
      ↓
REST inbound adapter
      ↓
inbound port
      ↓
application core
      ↓
outbound repository port
      ↓
PostgreSQL adapter
      ↓
orders table
```

It also uses Swagger UI and Swagger Codegen to show how a machine-readable API contract can support documentation and generated clients.

## Scope

These examples are teaching aids. They isolate one architectural decision at a time and are not complete FTGO implementations or production-ready configurations.
