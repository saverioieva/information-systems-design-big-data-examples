# API Versioning — Evolving an FTGO Order API

## Goal

Show how an API can evolve without breaking existing consumers, and compare two common ways to expose major API versions:

- **URI versioning** — the major version is part of the path;
- **media-type versioning** — the resource URI stays stable and the client selects the representation through the HTTP `Accept` header.

The lab also uses **semantic versioning** to distinguish compatible and incompatible contract changes.

> **Scope:** this lab intentionally focuses on API contract evolution. It does **not** model Hexagonal Architecture; that concern is isolated in the dedicated Hexagonal Architecture lab.

## Scenario

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

An existing v1 consumer can continue reading `id`, `status`, and `total` and ignore `deliveryEta`.

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

Existing v1 clients cannot read this contract unchanged, so it becomes API **2.0.0**.

## Two versioning strategies, same contracts

The gateway exposes the same v1 and v2 representations through two alternative public styles.

### URI versioning

```text
GET /v1/orders/123  -> v1 representation
GET /v2/orders/123  -> v2 representation
```

### Media-type versioning

```text
GET /orders/123
Accept: application/vnd.ftgo.order.v1+json

GET /orders/123
Accept: application/vnd.ftgo.order.v2+json
```

The resource URI remains `/orders/123`; the representation is selected through HTTP content negotiation.

```text
                    API Gateway
                   /           \
                  /             \
          URI versioning    Accept versioning
          /v1 or /v2         /orders/123
                  \             /
                   \           /
                    v         v
              Order API v1   Order API v2
                 1.1.0          2.0.0
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
    ├── client_v2.py
    └── client_media_type.py
```

## Run

From this directory:

```bash
docker compose up -d --build
```

Inspect the gateway entry point:

```bash
curl -s http://localhost:8083/
```

## 1. URI versioning — compatible v1 evolution

Call v1 and include response headers:

```bash
curl -i http://localhost:8083/v1/orders/123
```

Observe:

```text
Content-Type: application/json
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

The client reads only the fields it knows and ignores the additional field. This is a **MINOR** evolution because the existing v1 contract remains usable.

## 2. URI versioning — breaking v2 contract

```bash
curl -i http://localhost:8083/v2/orders/123
```

Observe:

```text
Content-Type: application/json
X-API-Version: 2.0.0
```

Run the v2 consumer:

```bash
python3 clients/client_v2.py
```

To prove that the new representation breaks the old consumer:

```bash
python3 clients/client_v1.py --url http://localhost:8083/v2/orders/123
```

The v1 client reports an incompatible contract because the fields it expects are no longer present.

## 3. Media-type versioning — same URI, v1 representation

Use the stable resource URI and request the v1 media type:

```bash
curl -i \
  -H 'Accept: application/vnd.ftgo.order.v1+json' \
  http://localhost:8083/orders/123
```

Observe:

```text
Content-Type: application/vnd.ftgo.order.v1+json
X-API-Version: 1.1.0
Vary: Accept
```

The payload is the same v1 representation exposed by `/v1/orders/123`.

## 4. Media-type versioning — same URI, v2 representation

```bash
curl -i \
  -H 'Accept: application/vnd.ftgo.order.v2+json' \
  http://localhost:8083/orders/123
```

Observe:

```text
Content-Type: application/vnd.ftgo.order.v2+json
X-API-Version: 2.0.0
Vary: Accept
```

The URI is unchanged, but the representation is now the breaking v2 contract.

You can also use the small client included in the repository:

```bash
python3 clients/client_media_type.py --version 1
python3 clients/client_media_type.py --version 2
```

## 5. Unsupported media types return 406

The media-type-versioned endpoint deliberately requires an explicit supported vendor media type:

```bash
curl -i \
  -H 'Accept: application/json' \
  http://localhost:8083/orders/123
```

Expected result:

```text
HTTP/1.1 406 Not Acceptable
```

This makes the content-negotiation contract visible instead of silently choosing a major version.

## 6. Why `Vary: Accept` matters

With media-type versioning, the same URI can produce different representations:

```text
/orders/123 + Accept: ...v1+json -> v1
/orders/123 + Accept: ...v2+json -> v2
```

The response therefore contains:

```http
Vary: Accept
```

This tells HTTP caches and intermediaries that responses for the same URI must be distinguished by the request's `Accept` header.

## 7. Inspect the contracts explicitly

```bash
curl -s http://localhost:8083/v1/contract
curl -s http://localhost:8083/v2/contract
```

The contract endpoints also report the associated vendor media type.

## URI vs media-type versioning

| Aspect | URI versioning | Media-type versioning |
|---|---|---|
| Example | `/v1/orders/123` | `/orders/123` + `Accept: ...v1+json` |
| Resource URI | Changes by major version | Remains stable |
| Version visibility | Explicit in URL | Explicit in HTTP headers |
| Browser/manual testing | Very simple | Requires setting `Accept` |
| Routing | Path-based | Content negotiation |
| Caching concern | Separate URLs naturally separate responses | `Vary: Accept` is important |
| Contract semantics | v1/v2 representation | Same v1/v2 representation |

The important point is that **versioning the contract** and **where the version is encoded** are separate design decisions.

## Semantic versioning in this example

| Change | Example | Version impact |
|---|---|---|
| Backward-compatible fix | Correct an implementation bug without changing the response contract | PATCH |
| Backward-compatible addition | Add optional `deliveryEta` | MINOR |
| Breaking contract change | Rename fields and change the representation of `total` | MAJOR |

The public URI, when URI versioning is used, normally contains the **major** version only. Clients should not have to change URLs for every minor or patch release.

Semantic software versions and public API major versions are related but distinct concepts:

```text
implementation release 1.8.4  !=  API major version v1
```

Multiple implementation releases can continue serving the same compatible API major version.

## Connection with deployment strategies

**API versioning and deployment versioning are related but are not the same thing.**

During a **rolling deployment**, old and new application instances can temporarily run at the same time. If they expose the same major API version, their contract should remain compatible throughout the rollout.

During a **blue-green deployment**, two complete application environments coexist before traffic is switched. This helps validate a new implementation, but it does not remove the need to keep v1 available while existing clients still depend on it.

For the deployment mechanics, compare this lab with:

- [`../../cloud-native-examples/rolling/`](../../cloud-native-examples/rolling/)
- [`../../cloud-native-examples/blue-green/`](../../cloud-native-examples/blue-green/)

> **Deployment strategies control how implementations are replaced; API versioning controls how contracts evolve.**

## What to observe

- v1 and v2 coexist behind the same gateway;
- `deliveryEta` is a backward-compatible addition within v1;
- the redesigned representation requires v2;
- URI and `Accept` versioning expose the **same contracts** using different HTTP interfaces;
- `Vary: Accept` is required to make media-type negotiation cache-aware;
- an unsupported media type can be rejected with `406 Not Acceptable`;
- tolerant v1 clients can ignore optional fields they do not understand.

## Clean up

```bash
docker compose down -v
```

## Scope

This example is intentionally minimal. Production API lifecycle management also involves deprecation policies, observability, authentication, documentation, schema governance, client migration, and retirement policies for old versions.
