# Resilience Patterns — Hexagonal API Gateway

This lab combines **Hexagonal Architecture** with three resilience patterns used in synchronous Remote Procedure Invocation (RPI):

- **Circuit Breaker** — implemented with `pybreaker`;
- **Retry** — implemented with `tenacity` and bounded exponential backoff;
- **Bulkhead** — an explicit per-dependency semaphore + dedicated thread pool;
- **HTTP timeout** — applied to each individual network attempt.

The scenario mirrors the four services used in the course slides:

```text
Client
  |
  | GET /orders/1001
  v
API Gateway
  |
  +---- Order Service
  +---- Kitchen Service
  +---- Delivery Service
  +---- Payment Service
```

The gateway aggregates the four responses. `Order Service` is required; the other dependencies may degrade independently.

> **Important:** the gateway follows Hexagonal Architecture. The resilience mechanisms belong to the **outbound side** of the gateway; the application core does not depend on FastAPI, HTTP, `requests`, PyBreaker, Tenacity, or thread pools.


## How to read this project before running it

Before looking at the Docker configuration or running the demos, follow one dependency from the application core to the network. This makes the relationship between **Hexagonal Architecture** and the resilience patterns much easier to see.

A useful reading path is:

```text
OrderCompositionService
        |
        | depends on
        v
KitchenGateway                     outbound port
        ^
        | implemented by
        |
KitchenHttpGateway                 outbound adapter
        |
        | delegates technical resilience to
        v
ResilientHttpClient
        |
        v
Bulkhead -> Circuit Breaker -> Retry -> HTTP timeout
        |
        v
Kitchen Service
```

The same structure is used for Order, Delivery, and Payment. Each dependency receives its **own** `ResilientHttpClient` and therefore its own bulkhead and circuit breaker. A slow Kitchen Service must not consume the execution capacity reserved for the other dependencies.

### Recommended classes to inspect

| File / class | What it shows | What to notice |
|---|---|---|
| `application/services/order_composition_service.py` — `OrderCompositionService` | Application core and graceful-degradation policy | It knows only application ports. It does not import FastAPI, `requests`, PyBreaker, Tenacity, semaphores, or thread pools. |
| `application/ports/outbound/kitchen_gateway.py` — `KitchenGateway` | Outbound port | The core asks for a Kitchen capability without knowing how the remote call is implemented. |
| `adapters/outbound/http/kitchen_http_gateway.py` — `KitchenHttpGateway` | Outbound HTTP adapter | It implements `KitchenGateway`, invokes `ResilientHttpClient`, and translates JSON into domain objects. |
| `infrastructure/resilience/resilient_http_client.py` — `ResilientHttpClient` | Composition of the resilience mechanisms | Follow the order `Bulkhead -> Circuit Breaker -> Retry -> timeout`. The libraries remain outside the application core. |
| `infrastructure/resilience/bulkhead.py` — `Bulkhead` | Resource isolation | Look at the bounded admission capacity, dedicated `ThreadPoolExecutor`, rejection counter, and `BulkheadRejectedError`. |
| `main.py` | Composition root | This is where concrete clients, HTTP adapters, cache, and `OrderCompositionService` are instantiated and connected. |

For the Bulkhead demo, also inspect `application/ports/inbound/dependency_probe_use_cases.py` and the diagnostic route. The probe is intentionally a teaching-only use case, but it still follows the normal architecture:

```text
HTTP diagnostic endpoint
        |
        v
DependencyProbeUseCases
        ^
        | implemented by
OrderCompositionService
        |
        v
KitchenGateway
        ^
        | implemented by
KitchenHttpGateway
        |
        v
ResilientHttpClient -> Bulkhead -> Kitchen Service
```

The diagnostic endpoint therefore does **not** call the Kitchen Service directly and does not bypass the outbound port or resilience layer.

### What the Bulkhead demo is trying to prove

The Kitchen Service can be configured to respond slowly using its teaching-only fault-control endpoint. The demo then sends several concurrent Kitchen probes so that the Kitchen bulkhead reaches its configured capacity:

```text
12 concurrent Kitchen calls
        |
        v
Kitchen bulkhead
maxConcurrency = 2
maxQueue       = 2
        |
        +--> 4 calls admitted
        |
        +--> remaining calls rejected quickly
```

While Kitchen is saturated, the demo also probes Order, Delivery, and Payment. Those calls should still succeed because they use **independent resilience stacks**:

```text
Kitchen bulkhead FULL        Order bulkhead      Delivery bulkhead      Payment bulkhead
        |                          |                    |                     |
        X reject excess           v                    v                     v
                              still available      still available       still available
```

This is the key Bulkhead property to observe: **resource exhaustion in one dependency is contained instead of propagating to unrelated service calls**.

When reading the logs, keep the responsibilities separate:

```text
Bulkhead        -> limits concurrent work and rejects excess load
Circuit Breaker -> stops calls after persistent failures
Retry           -> repeats transient failures a bounded number of times
Timeout         -> limits the duration of each individual HTTP attempt
```

The Bulkhead demo focuses on the first responsibility. Circuit Breaker and Retry are present in the same outbound stack, but they solve different failure modes.

---

## 1. Hexagonal architecture of the gateway

```text
                         External Client
                               |
                               | REST / JSON
                               v
+---------------------------------------------------------------------+
|                           API Gateway                               |
|                                                                     |
|  [REST inbound adapter]                                             |
|           |                                                         |
|           v                                                         |
|  (OrderCompositionUseCases)              inbound port               |
|           ^                                                         |
|           | implements                                              |
|  OrderCompositionService                  application core           |
|           |                                                         |
|           +----> (OrderGateway)                                     |
|           +----> (KitchenGateway)             outbound ports         |
|           +----> (DeliveryGateway)                                  |
|           +----> (PaymentGateway)                                   |
|           +----> (PaymentCache)                                     |
|                    ^                                                |
|                    | implements                                     |
|      +-------------+--------------------------------------------+   |
|      | HTTP outbound adapters                                  |   |
|      | Order / Kitchen / Delivery / Payment                    |   |
|      |                                                         |   |
|      | Bulkhead -> PyBreaker -> Tenacity -> HTTP timeout       |   |
|      +--------------------------|-------------------------------+   |
+---------------------------------|-----------------------------------+
                                  |
                 REST / JSON      |
       +--------------------------+--------------------------+
       v                          v                          v
 Order Service              Kitchen Service        Delivery / Payment
```

The dependency direction is **outside → inside**:

- the REST adapter invokes the inbound application port;
- `OrderCompositionService` implements the inbound ports;
- the application service depends only on outbound ports;
- the HTTP adapters implement those outbound ports;
- resilience libraries are infrastructure details used by the outbound HTTP adapters.

### Why this matters

The application core can express policies such as:

```text
Order unavailable   -> whole request fails
Kitchen unavailable -> partial response
Delivery unavailable-> partial response
Payment unavailable -> use cached payment if available
```

without knowing whether the remote call uses `requests`, retries, a circuit breaker, or a bulkhead.

---

## 2. Project structure

```text
gateway/
└── src/gateway/
    ├── domain/
    │   └── models.py
    ├── application/
    │   ├── ports/
    │   │   ├── inbound/
    │   │   │   ├── order_composition_use_cases.py
    │   │   │   └── dependency_probe_use_cases.py
    │   │   └── outbound/
    │   │       ├── order_gateway.py
    │   │       ├── kitchen_gateway.py
    │   │       ├── delivery_gateway.py
    │   │       ├── payment_gateway.py
    │   │       ├── payment_cache.py
    │   │       └── errors.py
    │   └── services/
    │       └── order_composition_service.py
    ├── adapters/
    │   ├── inbound/rest/
    │   │   ├── routes.py
    │   │   └── dto.py
    │   └── outbound/
    │       ├── http/
    │       │   ├── order_http_gateway.py
    │       │   ├── kitchen_http_gateway.py
    │       │   ├── delivery_http_gateway.py
    │       │   └── payment_http_gateway.py
    │       └── cache/
    │           └── in_memory_payment_cache.py
    ├── infrastructure/resilience/
    │   ├── resilient_http_client.py
    │   ├── circuit.py
    │   └── bulkhead.py
    └── main.py                         composition root
```

`main.py` only wires concrete adapters to ports.

---

## 3. Are the four internal services real REST APIs?

**Yes.** They are four independent FastAPI applications running in four separate containers and communicating with the gateway through real HTTP/JSON calls on the Docker network.

| Service | Host port | Business endpoint | Swagger UI |
|---|---:|---|---|
| Order | `8001` | `GET /orders/{orderId}` | `http://localhost:8001/docs` |
| Kitchen | `8002` | `GET /tickets/{orderId}` | `http://localhost:8002/docs` |
| Delivery | `8003` | `GET /deliveries/{orderId}` | `http://localhost:8003/docs` |
| Payment | `8004` | `GET /payments/{orderId}` | `http://localhost:8004/docs` |

For example, you can bypass the gateway and call Kitchen directly:

```bash
curl -s http://localhost:8002/tickets/1001
```

The result is returned by the actual Kitchen HTTP server, not by a fake object inside the gateway.

The services are intentionally simple because they act as **external systems** for the gateway lab. They also expose teaching-only REST endpoints for deterministic fault injection:

```text
GET  /health
GET  /admin/state
POST /admin/reset
POST /admin/delay/{milliseconds}
POST /admin/fail-next/{count}
```

These `/admin/*` operations are lab controls, not a recommended production API design.

---

## 4. Resilience stack used by each outbound HTTP adapter

Every downstream adapter owns an independent resilience stack:

```text
Application outbound port
          ^
          |
HTTP adapter
          |
          v
per-service Bulkhead
          |
          v
PyBreaker Circuit Breaker
          |
          v
Tenacity Retry Policy
          |
          v
requests HTTP timeout
          |
          v
REST service
```

The ordering is intentional:

- **bulkhead** first admits or rejects the complete logical call for one dependency;
- **circuit breaker** protects the admitted call and sees the final result of the retry operation;
- **retry** may repeat transient failures with exponential backoff;
- **timeout** bounds each individual network attempt.

> **PyBreaker implementation note:** `CircuitBreaker.call()` serializes the protected call with an internal lock. If the bulkhead is placed *inside* PyBreaker, concurrent callers are serialized before they can contend for bulkhead capacity and the bulkhead cannot be demonstrated correctly. For this lab the bulkhead admission therefore sits outside PyBreaker. Bulkhead rejections are also excluded from circuit-breaker failure counting.

---

## 5. Run the complete lab

The host needs only Docker and Docker Compose.

```bash
docker compose up --build -d
```

or:

```bash
make up
```

Follow the gateway logs:

```bash
docker compose logs -f gateway
```

Healthy API composition:

```bash
curl -s http://localhost:8000/orders/1001
```

Example response:

```json
{
  "order": {"orderId":"1001","status":"CONFIRMED","items":[...]},
  "kitchen": {"orderId":"1001","ticketId":"K-9001","status":"IN_PREP","station":"PIZZA"},
  "delivery": {"orderId":"1001","deliveryId":"D-5001","etaMinutes":25,"status":"PICKED_UP"},
  "payment": {"orderId":"1001","paymentId":"P-7001","amount":21.5,"currency":"EUR","method":"CARD","status":"PAID"},
  "degraded": false,
  "missing": [],
  "fallbacks": []
}
```

---

## 6. Retry — transient Kitchen failure

Reset Kitchen, then make exactly the next two calls fail:

```bash
curl -s -X POST http://localhost:8002/admin/reset
curl -s -X POST http://localhost:8002/admin/fail-next/2
```

Now issue **one** API-composition request:

```bash
curl -s http://localhost:8000/orders/1001
```

The Kitchen outbound adapter follows:

```text
Circuit CLOSED
      ↓
Attempt 1 -> HTTP 500
      ↓
backoff 0.2s
      ↓
Attempt 2 -> HTTP 500
      ↓
backoff 0.4s
      ↓
Attempt 3 -> 200 OK
      ↓
overall operation succeeds
```

Gateway logs expose the Tenacity attempts explicitly.

> Retry is limited to transient failures. A `404`, for example, is not retried.

---

## 7. Circuit Breaker — persistent Kitchen failure

Configure enough Kitchen failures to outlive the retry policy:

```bash
curl -s -X POST http://localhost:8002/admin/reset
curl -s -X POST http://localhost:8002/admin/fail-next/20
```

Default teaching configuration:

```text
retry attempts             = 3
circuit failure threshold  = 2 complete gateway operations
recovery timeout           = 5 seconds
```

Call the gateway twice:

```bash
curl -s http://localhost:8000/orders/1001
curl -s http://localhost:8000/orders/1001
```

Each gateway operation exhausts its retries and contributes one failure to PyBreaker. After the threshold is reached:

```text
CLOSED
  ↓ repeated failed operations
OPEN
  ↓
FAIL FAST
  ↓
no Retry
no Bulkhead acquisition
no HTTP request to Kitchen
```

Inspect the state:

```bash
curl -s http://localhost:8000/resilience
```

Kitchen is optional, so the public API can still return a degraded response with `"kitchen": null`.

### HALF_OPEN recovery

```bash
curl -s -X POST http://localhost:8002/admin/reset
sleep 6
curl -s http://localhost:8000/orders/1001
```

Expected transition:

```text
OPEN -> HALF_OPEN -> successful trial -> CLOSED
```

---

## 8. Bulkhead — isolate Kitchen overload

Each downstream adapter owns a separate bulkhead:

```text
Order      -> its own semaphore + thread pool
Kitchen    -> its own semaphore + thread pool
Delivery   -> its own semaphore + thread pool
Payment    -> its own semaphore + thread pool
```

There are two complementary ways to explore this pattern.

### Manual inspection with diagnostic endpoints

The teaching-only endpoints let you call exactly one downstream path from curl or Postman:

```text
GET /diagnostics/dependencies/order/1001
GET /diagnostics/dependencies/kitchen/1001
GET /diagnostics/dependencies/delivery/1001
GET /diagnostics/dependencies/payment/1001
```

They are **diagnostic endpoints**, not service proxies and not part of the business API. They still enter through an application inbound port and then use the normal outbound port, HTTP adapter, and resilience stack. The REST route never calls an HTTP client directly.

For example, you can manually slow Kitchen and inspect one call:

```bash
curl -s -X POST http://localhost:8002/admin/reset
curl -s -X POST http://localhost:8002/admin/delay/600
curl -i http://localhost:8000/diagnostics/dependencies/kitchen/1001
curl -s -X POST http://localhost:8002/admin/reset
```

### Reproducible Dockerized Bulkhead demo

For the classroom experiment, prefer the self-contained demo:

```bash
docker compose --profile tools run --rm bulkhead-demo
```

or:

```bash
make bulkhead-demo
```

The tool automatically:

```text
1. resets Kitchen and makes sure its circuit is healthy
2. configures Kitchen with a 600 ms delay
3. starts many concurrent Kitchen diagnostic calls
4. fills only the Kitchen bulkhead
5. probes Order, Delivery, and Payment while Kitchen is saturated
6. reports HTTP 429 rejections and the other services' responses
7. resets Kitchen when the experiment finishes
```

With the default configuration:

```text
Kitchen max concurrency = 2
Kitchen max queue       = 2
```

Before starting the load, the demo now prints the live Kitchen bulkhead configuration from `/resilience`. If these values are not `2` and `2`, rebuild/recreate the gateway before interpreting the result.

only four Kitchen operations can be admitted at the same time (two executing and two queued). Additional Kitchen calls are rejected with `429`, while Order, Delivery, and Payment retain their own independent capacity.

A successful run ends with output similar to:

```text
Bulkhead isolation demo
-----------------------
Kitchen requests:    12
Kitchen succeeded:    4
Kitchen rejected:     8 (HTTP 429)

Probes while Kitchen is busy
----------------------------
Order      HTTP 200
Delivery   HTTP 200
Payment    HTTP 200

Result
------
PASS: Kitchen saturation stayed inside the Kitchen bulkhead.
```

You can inspect the live counters separately at any time:

```bash
curl -s http://localhost:8000/resilience
```

---

## 9. Graceful degradation and Payment fallback

First perform a healthy call so the application stores the successful Payment in the `PaymentCache` outbound port:

```bash
curl -s http://localhost:8000/orders/1001 > /dev/null
```

Then fail Payment:

```bash
curl -s -X POST http://localhost:8004/admin/fail-next/20
```

Call the gateway again:

```bash
curl -s http://localhost:8000/orders/1001
```

The **application service**, not the HTTP adapter, decides that stale Payment data is acceptable:

```json
{
  "payment": {
    "paymentId": "P-7001",
    "status": "PAID",
    "source": "cache"
  },
  "degraded": true,
  "fallbacks": ["payment-cache"]
}
```

This separation is deliberate:

```text
How to call Payment resiliently?  -> outbound adapter / infrastructure
Can cached Payment be returned?   -> application policy
```

Reset Payment:

```bash
curl -s -X POST http://localhost:8004/admin/reset
```

---

## 10. Required vs optional dependencies

| Dependency | Application policy when unavailable |
|---|---|
| Order | Required: public API returns `503` |
| Kitchen | Optional: `null` + degraded response |
| Delivery | Optional: `null` + degraded response |
| Payment | Optional: cached fallback if available, otherwise `null` |

This policy lives in `OrderCompositionService`; it does not live in PyBreaker, Tenacity, or FastAPI.

---

## 11. What is library code and what is application architecture?

```text
pybreaker            Circuit Breaker implementation
Tenacity             Retry implementation
requests             HTTP client + timeout
Bulkhead             small explicit teaching implementation

OrderGateway          outbound application port
KitchenGateway        outbound application port
DeliveryGateway       outbound application port
PaymentGateway        outbound application port

*HttpGateway          outbound adapters
OrderCompositionService application core
FastAPI routes        inbound adapter
```

A generated or third-party resilience library does **not** replace the ports-and-adapters design. Libraries remain implementation details outside the core.

---

## 12. Test the application core without HTTP or resilience libraries

`tests/test_application_core.py` uses fake outbound adapters and tests the composition/fallback policy without FastAPI or real REST calls.

Run all tests in Docker:

```bash
make test
```

or:

```bash
docker compose run --rm gateway \
  python -m unittest discover -s /app/tests -v
```

The suite includes:

- application-core partial response with a fake failing Kitchen adapter;
- application-core Payment cache fallback;
- Tenacity retry behavior;
- PyBreaker `CLOSED -> OPEN -> HALF_OPEN -> CLOSED` behavior;
- Bulkhead rejection when execution + queue capacity are full.

---

## 13. Stop and clean up

```bash
docker compose down -v
```

or:

```bash
make down
```


