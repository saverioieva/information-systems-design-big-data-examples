# API Versioning — Evolving an FTGO Order API

## Goal

Show how an API can evolve without breaking existing consumers.

This lab focuses on three ideas:

- use **semantic versioning** to reason about compatible and incompatible contract changes;
- expose different **major API versions** side by side;
- understand why compatibility matters when old and new service implementations coexist during deployment.

The example intentionally keeps the business logic small so that the API contract remains the main focus.

## Scenario

Assume FTGO already exposes an Order API.

The original v1 contract contains:

```json
{
  "id": "123",
  "status": "CREATED",
  "total": 42.5
}
```

A backward-compatible change adds an optional delivery estimate. This becomes API **1.1.0**:

```json
{
  "id": "123",
  "status": "CREATED",
  "total": 42.5,
  "deliveryEta": "18:30"
}
```

An existing v1 consumer can continue reading `id`, `status`, and `total` and simply ignore `deliveryEta`.

A later redesign introduces breaking changes:

```json
{
  "id": "123",
  "orderStatus": "CREATED",
  "totalAmount": {
    "value": 42.5,
    "currency": "EUR"
  },
  "delivery": {
    "eta": "18:30"
  }
}
```

Because existing v1 clients cannot read this contract unchanged, it is exposed as API **2.0.0**.

## Architecture

```text
Client v1 ---- /v1 ----+
                       |
                       v
                  API Gateway
                       |
Client v2 ---- /v2 ----+
                   /         \
                  v           v
          Order API v1     Order API v2
             1.1.0            2.0.0
```

The gateway exposes only the **major version** in the public URI:

```text
GET /v1/orders/123
GET /v2/orders/123
```

The concrete semantic version is returned in the `X-API-Version` response header.

## Project structure

```text
api-versioning/
├── README.md
├── docker-compose.yml
├── gateway/
│   └── nginx.conf
├── order-v1/
│   ├── Dockerfile
│   ├── app.py
│   └── requirements.txt
├── order-v2/
│   ├── Dockerfile
│   ├── app.py
│   └── requirements.txt
└── clients/
    ├── client_v1.py
    └── client_v2.py
```

## Run

From this directory:

```bash
docker compose up -d --build
```

Check the gateway:

```bash
curl -s http://localhost:8083/
```

## 1. Inspect the backward-compatible v1 evolution

Call v1 and include the response headers:

```bash
curl -i http://localhost:8083/v1/orders/123
```

Observe:

```text
X-API-Version: 1.1.0
```

and the additional optional field:

```json
"deliveryEta": "18:30"
```

Run the old v1 consumer:

```bash
python3 clients/client_v1.py
```

The client reads only the fields it knows and reports that the additional field was ignored.

This demonstrates a **MINOR** evolution: the API added functionality while preserving the existing v1 contract.

## 2. Inspect the breaking v2 contract

Call the new major version:

```bash
curl -i http://localhost:8083/v2/orders/123
```

Observe:

```text
X-API-Version: 2.0.0
```

The contract now uses `orderStatus`, a structured `totalAmount`, and a `delivery` object.

Run the v2 consumer:

```bash
python3 clients/client_v2.py
```

## 3. Prove that the v2 contract breaks a v1 client

Point the v1 client at the v2 endpoint:

```bash
python3 clients/client_v1.py --url http://localhost:8083/v2/orders/123
```

The client reports an incompatible contract because the fields it expects are no longer present.

This is why the change requires a new **MAJOR** API version rather than silently replacing v1.

## 4. Inspect the contracts explicitly

```bash
curl -s http://localhost:8083/v1/contract
curl -s http://localhost:8083/v2/contract
```

The endpoints summarize why `1.1.0` is compatible within v1 and why `2.0.0` is a breaking change.

## Semantic versioning in this example

| Change | Example | Version impact |
|---|---|---|
| Backward-compatible fix | Correct an implementation bug without changing the response contract | PATCH |
| Backward-compatible addition | Add optional `deliveryEta` | MINOR |
| Breaking contract change | Rename fields and change the representation of `total` | MAJOR |

The public URI normally contains the **major** version only. Clients should not have to change URLs for every minor or patch release.

## Connection with deployment strategies

**API versioning and deployment versioning are related but are not the same thing.**

During a **rolling deployment**, old and new application instances can temporarily run at the same time. If they expose the same major API version, their contract should remain compatible throughout the rollout.

During a **blue-green deployment**, two complete application environments coexist before traffic is switched. This makes it easier to validate a new implementation, but it does not remove the need for API compatibility when existing clients still depend on v1.

For the deployment mechanics, compare this lab with:

- [`../../cloud-native-examples/rolling/`](../../cloud-native-examples/rolling/)
- [`../../cloud-native-examples/blue-green/`](../../cloud-native-examples/blue-green/)

A useful rule is:

> **Deployment strategies control how implementations are replaced; API versioning controls how contracts evolve.**

## What to observe

- v1 and v2 can coexist behind the same gateway.
- A compatible change does **not** require a new major URI.
- A breaking contract is published separately instead of silently replacing the old contract.
- Tolerant clients can ignore optional fields they do not understand.
- Compatibility is especially important while multiple implementation versions coexist during deployment.

## Clean up

```bash
docker compose down -v
```

## Scope

This example is intentionally minimal. Production API lifecycle management also involves deprecation policies, observability, authentication, documentation, schema governance, and a migration plan for retiring old versions.
