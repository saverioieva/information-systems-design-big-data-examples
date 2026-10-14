# API Versioning — Evolving an FTGO Order API

## Goal

Show how a published REST API can evolve without forcing clients to change for every software release.

The lab compares two ways to expose **major API versions**:

- **URI versioning** — `/v1/...` and `/v2/...`;
- **media-type versioning** — stable URI plus a versioned HTTP `Accept` media type.

It also makes the distinction between **API contract version** and **service/software version** concrete by demonstrating `PATCH`, `MINOR`, and `MAJOR` evolution.

> **Scope:** this lab focuses on API contract evolution. It intentionally does **not** model Hexagonal Architecture; that concern is isolated in the dedicated Hexagonal Architecture lab.

## The key distinction

A public major API version and a software release are related, but they are not the same thing.

```text
Public API contract            Service release
-----------------              ---------------
v1                             1.0.0
v1                             1.1.0
v1                             1.1.1

v2                             2.0.0
```

The client does **not** need a new URI for every compatible release.

The responses make this distinction visible:

```http
X-API-Version: 1
X-Service-Version: 1.1.1
```

For media-type versioning, the same idea is visible in the representation type:

```http
Content-Type: application/vnd.ftgo.order.v1+json
X-Service-Version: 1.1.1
```

## Scenario: PATCH, MINOR, MAJOR

### 1.0.0 — original v1 contract

```json
{
  "id": "123",
  "status": "CREATED",
  "total": 42.5
}
```

### 1.1.0 — MINOR evolution

A backward-compatible feature adds the optional `deliveryEta` field:

```json
{
  "id": "123",
  "status": "CREATED",
  "total": 42.5,
  "deliveryEta": "8:05"
}
```

Old v1 consumers can keep reading `id`, `status`, and `total` and ignore the additional field.

This release intentionally contains a small formatting bug: the ETA is not zero-padded.

### 1.1.1 — PATCH evolution

The formatting bug is fixed:

```json
{
  "id": "123",
  "status": "CREATED",
  "total": 42.5,
  "deliveryEta": "08:05"
}
```

The request URI and the response schema are unchanged from `1.1.0`. This is the important PATCH-version lesson:

> **A patch release fixes the implementation without creating a new public API contract.**

### 2.0.0 — MAJOR evolution

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
    "eta": "08:05"
  }
}
```

Existing v1 clients cannot consume this representation unchanged, so a new **v2** contract is required.

## Two versioning strategies, same contracts

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

The resource URI remains `/orders/123`; the major representation is selected through HTTP content negotiation.

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
             service release    2.0.0
          1.0.0 / 1.1.0 / 1.1.1
```

## Project structure

```text
api-versioning/
├── README.md
├── Makefile
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

## Run the default stack

The default v1 service release is the latest compatible release, `1.1.1`:

```bash
docker compose up -d --build
```

Equivalent Make target:

```bash
make up
```

Inspect the gateway entry point:

```bash
curl -s -w '\n' http://localhost:8083/
```

## 1. Observe the MINOR evolution

Start the original `1.0.0` release:

```bash
make run-v1.0.0
```

Call exactly the same public v1 endpoint:

```bash
curl -i -w '\n' http://localhost:8083/v1/orders/123
```

Observe:

```text
X-API-Version: 1
X-Service-Version: 1.0.0
```

and the original three-field representation.

Now deploy the compatible `1.1.0` release:

```bash
make run-v1.1.0
```

Call the **same** endpoint again:

```bash
curl -i -w '\n' http://localhost:8083/v1/orders/123
```

Observe:

```text
X-API-Version: 1
X-Service-Version: 1.1.0
```

and the new optional field:

```json
"deliveryEta": "8:05"
```

The public API is still **v1**. The service release changed from `1.0.0` to `1.1.0` because a backward-compatible feature was added.

Run the old v1 consumer in Docker:

```bash
make client-v1
```

It still works because it reads only the fields it knows and ignores the new optional field. This illustrates a tolerant consumer; clients that reject unknown JSON fields would need their own compatibility policy.

## 2. Observe a real PATCH release

The `1.1.0` release has an intentionally visible bug: `deliveryEta` is not zero-padded.

Deploy `1.1.1`:

```bash
make run-v1.1.1
```

Call exactly the same endpoint:

```bash
curl -i -w '\n' http://localhost:8083/v1/orders/123
```

Now observe:

```text
X-API-Version: 1
X-Service-Version: 1.1.1
```

and:

```json
"deliveryEta": "08:05"
```

Nothing changed from the client's API-versioning point of view:

```text
/v1/orders/123              unchanged
fields                      unchanged from 1.1.0
media type                  unchanged
client code                 unchanged
```

Only the implementation release changed:

```text
1.1.0  ->  1.1.1
 bug         fix
```

That is why there is **no `/v1.1.1` endpoint**.

## 3. Observe the breaking MAJOR evolution

```bash
curl -i -w '\n' http://localhost:8083/v2/orders/123
```

Observe:

```text
X-API-Version: 2
X-Service-Version: 2.0.0
```

Run the v2 consumer in Docker:

```bash
make client-v2
```

To prove that the new representation breaks the old consumer:

```bash
docker compose --profile tools run --rm client \
  python client_v1.py --url http://api-gateway/v2/orders/123
```

The v1 client reports an incompatible contract because the fields it expects are no longer present.

## 4. Media-type versioning — same URI, v1 representation

The same v1 contract can be selected without putting the major version in the URI:

```bash
curl -i -w '\n' \
  -H 'Accept: application/vnd.ftgo.order.v1+json' \
  http://localhost:8083/orders/123
```

With `1.1.1` active, observe:

```text
Content-Type: application/vnd.ftgo.order.v1+json
X-API-Version: 1
X-Service-Version: 1.1.1
Vary: Accept
```

If you switch back to `1.1.0`, the `Accept` value remains exactly the same; only `X-Service-Version` and the bug fix differ.

## 5. Media-type versioning — same URI, v2 representation

```bash
curl -i -w '\n' \
  -H 'Accept: application/vnd.ftgo.order.v2+json' \
  http://localhost:8083/orders/123
```

Observe:

```text
Content-Type: application/vnd.ftgo.order.v2+json
X-API-Version: 2
X-Service-Version: 2.0.0
Vary: Accept
```

You can also use the included Dockerized client:

```bash
make client-media-v1
make client-media-v2
```

## 6. Unsupported media types return 406

The media-type-versioned endpoint requires an explicit supported vendor media type:

```bash
curl -i -w '\n' \
  -H 'Accept: application/json' \
  http://localhost:8083/orders/123
```

Expected result:

```text
HTTP/1.1 406 Not Acceptable
```

## 7. Why `Vary: Accept` matters

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

## 8. Inspect the contracts explicitly

```bash
curl -s -w '\n' http://localhost:8083/v1/contract
curl -s -w '\n' http://localhost:8083/v2/contract
```

The v1 contract endpoint reports both the public API major and the currently running service release.

For example, with `1.1.1` active:

```json
{
  "apiMajorVersion": "1",
  "serviceVersion": "1.1.1",
  "mediaType": "application/vnd.ftgo.order.v1+json",
  "compatibility": "backward-compatible within v1"
}
```

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

The important point is that **versioning the contract** and **where the major version is encoded** are separate design decisions.

## Semantic versioning in this example

| Transition | What changes | API major | Meaning |
|---|---|---:|---|
| `1.0.0 -> 1.1.0` | Optional `deliveryEta` is added | `v1` | **MINOR**: compatible feature |
| `1.1.0 -> 1.1.1` | ETA formatting bug is fixed | `v1` | **PATCH**: same contract |
| `1.x -> 2.0.0` | Fields are renamed/restructured | `v2` | **MAJOR**: breaking contract |

Conceptually:

```text
1.0.0
  |
  | backward-compatible feature
  v
1.1.0              MINOR
  |
  | bug fix, same schema
  v
1.1.1              PATCH
  |
  | breaking contract change
  v
2.0.0              MAJOR -> public API v2
```

## API versioning vs deployment versioning

API versioning and deployment versioning are related, but they are not the same thing.

A rolling or blue-green deployment can temporarily run different **service releases** at the same time. If those releases all expose API `v1`, they must remain compatible with the v1 contract during the rollout.

```text
API v1
  |- service 1.1.0
  `- service 1.1.1

same public major contract
```

Deployment strategies control **how implementations are replaced**; API versioning controls **how published contracts evolve**.

## What to observe

- `/v1` does not become `/v1.1.0` or `/v1.1.1`;
- `1.0.0 -> 1.1.0` is a compatible feature addition;
- `1.1.0 -> 1.1.1` is a true PATCH example with the same response schema;
- `v2` is introduced only for a breaking contract change;
- URI and `Accept` versioning expose the same major contracts through different HTTP interfaces;
- `X-API-Version` reports the public major contract while `X-Service-Version` reports the concrete implementation release;
- `Vary: Accept` makes content negotiation cache-aware;
- tolerant v1 clients can ignore optional fields they do not understand.

## Clean up

```bash
make down
```

or:

```bash
docker compose down -v
```

## Scope

This example is intentionally minimal. Production API lifecycle management also involves deprecation policies, observability, authentication, documentation, schema governance, client migration, and retirement policies for old versions.
