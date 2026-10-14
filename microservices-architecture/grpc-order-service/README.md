# gRPC Service Integration: compare REST and gRPC inside a Hexagonal design

This lab demonstrates **service-to-service communication** between two different microservices and then turns the same Unary interaction into a small REST-vs-gRPC experiment.

- an external **Checkout Service** exposes REST/JSON through FastAPI;
- Checkout needs stock information from a separate internal **Inventory Service**;
- Checkout defines an application-owned `InventoryGateway` outbound port;
- one Checkout deployment implements that port with `GrpcInventoryClient`;
- a second Checkout deployment implements the same port with `RestInventoryClient`;
- Inventory exposes the same `InventoryUseCases` through two inbound adapters: **gRPC** and **REST**;
- the gRPC contract is defined in `proto/inventory.proto` and generated **inside Docker images**; an optional Dockerized codegen profile can also materialize the generated service plumbing under `generated/` for inspection;
- Inventory keeps persistence behind an `InventoryRepository` outbound port, implemented here by an in-memory adapter;
- **Prometheus** collects client-side latency and serialized payload-size metrics for the REST and gRPC variants;
- **Postman** can call the external REST APIs, the internal Inventory REST adapter, and the internal gRPC endpoint;
- an optional **TShark container** can inspect the application traffic reaching both Inventory adapters (REST on `8081`, gRPC on `50051`) without installing Wireshark on the host; Prometheus `/metrics` traffic is intentionally excluded.

The main teaching point is not that one protocol is always better. The lab shows that **the same application core can be reached through different adapters**, and that protocol trade-offs should be **measured rather than assumed**.

> **Docker-first lab:** students need Docker + Docker Compose for the application, code generation, tests, comparison workload, Prometheus, and TShark. Postman Desktop is optional but recommended for graphical exploration. No local Python, `pip`, `protoc`, `grpcio-tools`, Prometheus, Wireshark, or TShark installation is required.

---

## Architecture

The public API stays REST in both deployments. Only the **internal Checkout → Inventory collaboration** changes.

```text
                              same public contract

External client                 External client
      |                               |
      | REST / JSON                   | REST / JSON
      v                               v
+---------------------+       +---------------------+
| Checkout Service    |       | Checkout Service    |
| deployment A        |       | deployment B        |
| :8000               |       | :8001               |
|                     |       |                     |
| REST adapter        |       | REST adapter        |
|      |              |       |      |              |
| CheckoutUseCases    |       | CheckoutUseCases    |
|      ^              |       |      ^              |
|      |              |       |      |              |
| CheckoutApplication|       | CheckoutApplication|
| Service             |       | Service             |
|      |              |       |      |              |
| InventoryGateway    |       | InventoryGateway    |
|      ^              |       |      ^              |
|      |              |       |      |              |
| GrpcInventoryClient|       | RestInventoryClient |
+------|--------------+       +------|--------------+
       |                             |
       | gRPC / HTTP/2               | HTTP / JSON
       | Protocol Buffers            |
       v                             v
+----------------------------------------------------------+
| Inventory Service                                        |
|                                                          |
| GrpcInventoryAdapter         RestInventoryAdapter        |
|          |                           |                   |
|          +------------+--------------+                   |
|                       v                                  |
|               InventoryUseCases          inbound port    |
|                       ^                                  |
|                       |                                  |
|          InventoryApplicationService      application    |
|                       |                    core          |
|                       v                                  |
|               InventoryRepository         outbound port  |
|                       ^                                  |
|                       |                                  |
|          InMemoryInventoryRepository      outbound       |
|                                            adapter       |
+----------------------------------------------------------+
```

The key Hexagonal Architecture observations are:

- Checkout's application core depends on `InventoryGateway`, not on REST or gRPC;
- `GrpcInventoryClient` and `RestInventoryClient` are alternative **outbound adapters** implementing the same Checkout port;
- Inventory's `GrpcInventoryAdapter` and `RestInventoryAdapter` are alternative **inbound adapters** invoking the same `InventoryUseCases`;
- both Inventory adapters reach the same `InventoryApplicationService` and the same repository instance;
- generated gRPC classes and Pydantic models remain transport-level objects outside the application core.

This is still a collaboration between **two different services**. The second Inventory REST adapter is added only so the same Unary use case can be compared with gRPC without changing the business logic.

### Persistence scope: why Inventory uses an in-memory repository

Inventory has a real outbound port and a real outbound adapter, but intentionally does **not** use a real database in this lab:

```text
InventoryApplicationService
        |
        v
InventoryRepository            outbound port
        ^
        |
InMemoryInventoryRepository    outbound adapter
```

| Element | Present in this lab? |
|---|---|
| `InventoryRepository` outbound port | Yes |
| Concrete repository adapter | Yes |
| Real database such as PostgreSQL | No |
| Persistent storage across restarts | No |

Persistence is deliberately simplified because the previous Hexagonal Architecture lab already demonstrates a PostgreSQL adapter. If durable storage were required, `InMemoryInventoryRepository` could be replaced by `PostgresInventoryRepository` without changing `InventoryApplicationService`.

> **Teaching point:** the in-memory repository is still a concrete outbound adapter. The simplification is the persistence technology, not the architectural boundary.

---

## Prerequisites

For the complete lab you need:

- **Docker** with Docker Compose;
- **Postman Desktop** only if you want the graphical REST/gRPC demonstrations.

Postman Desktop can be downloaded from:

- <https://www.postman.com/downloads/>

The desktop application is preferable because the services run on `localhost`.

---

## Repository layout

```text
grpc-order-service/
├── proto/
│   └── inventory.proto
├── checkout-service/
│   ├── src/checkout_service/
│   │   ├── domain/
│   │   ├── application/
│   │   │   ├── ports/
│   │   │   └── services/
│   │   ├── metrics.py
│   │   └── adapters/
│   │       ├── inbound/rest/
│   │       └── outbound/
│   │           ├── grpc/
│   │           └── rest/
│   ├── Dockerfile
│   └── requirements.txt
├── inventory-service/
│   ├── src/inventory_service/
│   │   ├── domain/
│   │   ├── application/
│   │   │   ├── ports/
│   │   │   └── services/
│   │   └── adapters/
│   │       ├── inbound/
│   │       │   ├── grpc/
│   │       │   └── rest/
│   │       └── outbound/memory/
│   ├── Dockerfile
│   └── requirements.txt
├── observability/
│   └── prometheus.yml
├── demo-clients/
│   ├── compare_unary.py
│   ├── unary.py
│   ├── server_streaming.py
│   ├── client_streaming.py
│   └── bidirectional.py
├── tests/
│   └── Dockerfile
├── tools/
│   └── grpc-codegen.Dockerfile
├── docker-compose.yml
└── Makefile
```

Generated Protocol Buffer Python files are created during Docker image builds and are **not committed to Git**. The optional `codegen` profile can also write a disposable copy to `generated/` so students can inspect the generated server/client plumbing directly.

---

## 1. Start from the `.proto` contract

`proto/inventory.proto` is the source of truth for the gRPC Inventory API.

```proto
service InventoryService {
  rpc CheckAvailability(CheckAvailabilityRequest) returns (AvailabilityReply);
  rpc WatchStock(WatchStockRequest) returns (stream StockUpdate);
  rpc CheckMany(stream CheckAvailabilityRequest) returns (BatchAvailabilityReply);
  rpc InventorySession(stream InventoryCommand) returns (stream InventoryEvent);
}
```

The same contract demonstrates all four gRPC interaction models:

| Interaction model | RPC | Shape |
|---|---|---|
| Unary | `CheckAvailability` | one request → one response |
| Server Streaming | `WatchStock` | one request → many responses |
| Client Streaming | `CheckMany` | many requests → one response |
| Bidirectional Streaming | `InventorySession` | many requests ↔ many responses |

A Unary operation is defined by a service, an RPC, and typed messages:

```proto
service InventoryService {
  rpc CheckAvailability(CheckAvailabilityRequest) returns (AvailabilityReply);
}

message CheckAvailabilityRequest {
  string sku = 1;
  int32 quantity = 2;
}
```

The numeric field tags are part of the wire contract. New compatible fields should use new tags, and removed tags should not be reused.

---

## 2. Code generation happens inside Docker

There is **no host-side code-generation step** in the normal workflow.

The service Dockerfiles compile `proto/inventory.proto` during image build:

```text
inventory.proto
      |
      | grpc_tools.protoc inside Docker
      v
+-------------------------+
| inventory_pb2.py        |  generated message classes
| inventory_pb2_grpc.py   |  generated stub/server plumbing
+-------------------------+
```

Conceptually:

```bash
python -m grpc_tools.protoc \
  -I/app/proto \
  --python_out=/app/generated \
  --grpc_python_out=/app/generated \
  /app/proto/inventory.proto
```

Generated code is transport plumbing. Business logic should not be added to generated files.

> The generated gRPC stub is **not** an application port, and generated Protocol Buffer messages are **not** domain models.

### 2.1 Optional: materialize the generated gRPC service plumbing

The normal runtime already performs code generation while building the service images. For teaching, the repository also provides an optional Dockerized code-generation profile that writes the generated Python files into the host-visible, Git-ignored `generated/` directory:

```bash
make generate-grpc-skeleton
```

or equivalently:

```bash
docker compose --profile codegen run --rm grpc-codegen
```

This produces:

```text
generated/
├── inventory_pb2.py
└── inventory_pb2_grpc.py
```

Open `inventory_pb2_grpc.py` and look for the generated service-side plumbing:

```text
InventoryServiceStub
InventoryServiceServicer
add_InventoryServiceServicer_to_server(...)
```

Then compare it with the handwritten Inventory adapter:

```text
inventory.proto
      |
      | grpc_tools.protoc in a Docker container
      v
InventoryServiceServicer          generated transport interface
      ^
      | subclassed by
GrpcInventoryAdapter              handwritten inbound adapter
      |
      v
InventoryUseCases                 application inbound port
      ^
      | implemented by
InventoryApplicationService       application core
```

The distinction is important: **`InventoryServiceServicer` is generated protocol/framework plumbing, not the Hexagonal inbound port**. The generated class knows gRPC method signatures; `InventoryUseCases` expresses what the application offers independently of gRPC.

The same generated module also contains the client-side `InventoryServiceStub`. Checkout's application core still does not depend on that generated stub directly: `GrpcInventoryClient` wraps it behind the application-owned `InventoryGateway` port.

> **Runtime isolation:** this optional command does not replace the code generated inside the existing Docker images and it does not change the running services. The files under `generated/` exist only so they can be inspected and compared with the handwritten adapters.

To delete the inspection copy:

```bash
make clean-generated
```

---

## 3. Compare interchangeable adapters

### Checkout: one outbound port, two outbound adapters

Checkout owns this abstraction:

```python
class InventoryGateway(ABC):
    @abstractmethod
    def check_availability(self, sku: str, quantity: int) -> InventoryAvailability:
        ...
```

Two adapters implement it:

```text
CheckoutApplicationService
          |
          v
   InventoryGateway             outbound port
       ^          ^
       |          |
       |          +---- RestInventoryClient
       |
       +--------------- GrpcInventoryClient
```

`checkout-grpc` is configured with:

```text
INVENTORY_PROTOCOL=grpc
```

while `checkout-rest` uses:

```text
INVENTORY_PROTOCOL=rest
```

The **Checkout application service is identical** in both containers. The deployment configuration selects only the outbound adapter.

### Inventory: two inbound adapters, one inbound port

Inventory exposes the same Unary application use case through two transport adapters:

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
```

The gRPC adapter translates generated Protocol Buffer messages. The REST adapter translates HTTP/JSON + Pydantic DTOs. Neither transport type leaks into the core.

The gRPC adapter additionally exposes the three streaming RPCs. The REST adapter intentionally implements only the availability request needed for the Unary comparison.

---

## 4. DTOs vs domain models

Transport objects stay at transport boundaries.

### REST boundary

```text
HTTP / JSON
    |
    v
Pydantic DTO
    |
    v
REST adapter
    |
    v
application port
```

Pydantic models represent HTTP request/response schemas, validation, serialization, and OpenAPI documentation. They are **not** domain entities.

### gRPC boundary

```text
gRPC / Protocol Buffers
        |
        v
generated protobuf message
        |
        v
gRPC adapter
        |
        v
application port
```

Generated Protocol Buffer message classes play the analogous transport-level role at the gRPC boundary.

```text
Pydantic models       -> REST transport DTOs
Protobuf messages     -> gRPC transport DTOs
Domain objects/ports  -> application and domain layers
```

---

## 5. Run the complete stack

Start everything:

```bash
docker compose up --build -d
```

Check it:

```bash
docker compose ps
```

Available endpoints:

| Component | Address | Purpose |
|---|---|---|
| Checkout using internal gRPC | `http://localhost:8000` | Public REST API, gRPC outbound adapter |
| Checkout using internal REST | `http://localhost:8001` | Same public REST API, REST outbound adapter |
| Inventory gRPC | `localhost:50051` | Unary + three streaming RPCs |
| Inventory REST | `http://localhost:8081` | REST adapter for the same availability use case |
| Inventory REST Swagger UI | `http://localhost:8081/docs` | Interactive REST contract |
| Prometheus | `http://localhost:9090` | Metrics comparison |

The Inventory ports are exposed to the host for teaching purposes. In a real deployment, internal service endpoints would commonly remain private to the service network.

---

## 6. Main experiment: same Checkout API, different internal protocol

Send the **same request** to both Checkout deployments.

### 6.1 Checkout using gRPC internally

```bash
curl -s -X POST http://localhost:8000/checkouts \
  -H 'Content-Type: application/json' \
  -d '{"sku":"pizza","quantity":2}'
```

Path:

```text
REST client
    |
    v
Checkout REST adapter
    |
    v
CheckoutApplicationService
    |
    v
InventoryGateway
    |
    v
GrpcInventoryClient
    |
    | Unary CheckAvailability
    | gRPC + HTTP/2 + Protocol Buffers
    v
GrpcInventoryAdapter
    |
    v
InventoryUseCases
```

### 6.2 Checkout using REST internally

```bash
curl -s -X POST http://localhost:8001/checkouts \
  -H 'Content-Type: application/json' \
  -d '{"sku":"pizza","quantity":2}'
```

Path:

```text
REST client
    |
    v
Checkout REST adapter
    |
    v
CheckoutApplicationService
    |
    v
InventoryGateway
    |
    v
RestInventoryClient
    |
    | POST /availability
    | HTTP + JSON
    v
RestInventoryAdapter
    |
    v
InventoryUseCases
```

Both should return the same public result, for example:

```json
{
  "sku": "pizza",
  "quantity": 2,
  "availableQuantity": 8,
  "status": "ACCEPTED"
}
```

The important experimental property is:

```text
same external request
same Checkout core
same Inventory core
same business data

only the internal transport adapter changes
```

### 6.3 Call the internal Inventory REST adapter directly

For comparison, the REST adapter on Inventory can also be invoked directly:

```bash
curl -s -X POST http://localhost:8081/availability \
  -H 'Content-Type: application/json' \
  -d '{"sku":"pizza","quantity":2}'
```

Example response:

```json
{
  "sku": "pizza",
  "requestedQuantity": 2,
  "availableQuantity": 8,
  "available": true
}
```

---

## 7. Test the REST APIs with Postman

Postman can be used as a normal HTTP client for both Checkout deployments.

Create a request:

```text
POST http://localhost:8000/checkouts
```

Body → raw → JSON:

```json
{
  "sku": "pizza",
  "quantity": 2
}
```

Then send exactly the same request to:

```text
POST http://localhost:8001/checkouts
```

The public response should be equivalent; the internal protocol is different.

### Import the OpenAPI document into Postman

FastAPI exposes an OpenAPI document automatically. In Postman:

```text
Import
  -> Link
  -> http://localhost:8000/openapi.json
```

Postman can generate a collection from the REST contract. To exercise the REST-internal deployment, reuse the same request and change the base URL from port `8000` to `8001`.

You can also inspect the Inventory REST adapter through:

```text
http://localhost:8081/docs
```

or import:

```text
http://localhost:8081/openapi.json
```

---

## 8. Explore gRPC graphically with Postman

With the stack running:

1. Open **Postman Desktop**.
2. Select **New → gRPC**.
3. Enter:

```text
localhost:50051
```

4. Leave TLS disabled for this local lab.
5. Select a method from `ftgo.inventory.v1.InventoryService`.

The Inventory Service enables **gRPC server reflection**, so Postman should discover the service. If needed, import `proto/inventory.proto` manually.

### 8.1 Unary — `CheckAvailability`

```json
{
  "sku": "pizza",
  "quantity": 2
}
```

This is the same application use case used by both Checkout variants.

### 8.2 Server Streaming — `WatchStock`

```json
{
  "sku": "pizza"
}
```

One request produces multiple server messages.

### 8.3 Client Streaming — `CheckMany`

Open the stream and send several messages, for example:

```json
{"sku":"pizza","quantity":2}
```

```json
{"sku":"pasta","quantity":5}
```

```json
{"sku":"salad","quantity":1}
```

Then end the stream. The server returns one `BatchAvailabilityReply`.

### 8.4 Bidirectional Streaming — `InventorySession`

Open the stream and send commands such as:

```json
{"sku":"pizza","action":"check","quantity":1}
```

```json
{"sku":"pizza","action":"reserve","quantity":2}
```

```json
{"sku":"pizza","action":"release","quantity":1}
```

The client and server can continue exchanging messages on the same open session.

### Why the REST comparison focuses on Unary

A normal HTTP request/response maps naturally to the Unary RPC. The three streaming models are intentionally tested directly through gRPC because reproducing them through REST would require additional mechanisms such as SSE, chunked streaming, or WebSockets and would change the lesson.

---

## 9. Compare REST and gRPC with Prometheus

Prometheus is included as a **teaching/diagnostic collector**, not as an application component.

The metrics are recorded by the Checkout outbound adapters, which means the measurement point is the same logical place for both protocols:

```text
CheckoutApplicationService
        |
        v
InventoryGateway
        |
        +---- GrpcInventoryClient ----> metrics(protocol="grpc")
        |
        +---- RestInventoryClient ----> metrics(protocol="rest")
```

The adapters expose:

| Metric | Meaning |
|---|---|
| `inventory_client_duration_seconds` | Checkout-observed duration of the remote Inventory call |
| `inventory_client_request_payload_bytes` | serialized application request payload bytes |
| `inventory_client_response_payload_bytes` | serialized application response payload bytes |
| `inventory_client_requests_total` | successful/failed calls by protocol |

Prometheus scrapes:

```text
http://checkout-grpc:8000/metrics
http://checkout-rest:8000/metrics
```

From the host, the raw metrics are also visible at:

```text
http://localhost:8000/metrics
http://localhost:8001/metrics
```

### 9.1 Generate a small comparison workload

The repository includes a Dockerized comparison client. It sends the same checkout request repeatedly to both deployments:

```bash
docker compose --profile tools run --rm grpc-client compare_unary.py
```

or:

```bash
make compare
```

By default it performs 50 requests per variant. To change the count:

```bash
docker compose --profile tools run --rm \
  -e REQUEST_COUNT=200 \
  grpc-client compare_unary.py
```

### 9.2 Open Prometheus

Open:

```text
http://localhost:9090
```

Useful queries follow.

**Average Inventory-call latency since process start**

```promql
sum by (protocol) (inventory_client_duration_seconds_sum)
/
sum by (protocol) (inventory_client_duration_seconds_count)
```

**Average serialized request payload size**

```promql
sum by (protocol) (inventory_client_request_payload_bytes_sum)
/
sum by (protocol) (inventory_client_request_payload_bytes_count)
```

**Average serialized response payload size**

```promql
sum by (protocol) (inventory_client_response_payload_bytes_sum)
/
sum by (protocol) (inventory_client_response_payload_bytes_count)
```

**Calls by protocol and result**

```promql
sum by (protocol, status) (inventory_client_requests_total)
```

### What exactly is being measured?

For REST, payload size is the actual JSON body serialized by `RestInventoryClient` and the JSON response body received from Inventory.

For gRPC, payload size is the serialized Protocol Buffer message:

```python
len(message.SerializeToString())
```

Therefore the payload comparison is intentionally:

```text
JSON serialized application payload
vs
Protocol Buffer serialized application payload
```

It does **not** include all bytes on the wire.

REST additionally has HTTP headers. gRPC adds its 5-byte message prefix, HTTP/2 framing, and HTTP/2 headers. Use the TShark section below when the goal is to inspect actual transport traffic.

### Interpreting the latency result

Do not design the experiment to prove that gRPC is always faster.

The latency experiment compares the **real stacks used by this lab**: the REST adapter uses HTTP/JSON through the normal FastAPI/Uvicorn HTTP stack, while gRPC uses HTTP/2 + Protocol Buffers. It is therefore an end-to-end protocol-stack comparison, not a microbenchmark that isolates one variable such as serialization cost.

On `localhost`, with tiny messages and a very small service, latency differences can be small, noisy, or even counter-intuitive. The more robust observation is usually that Protocol Buffers produce a more compact serialized payload than equivalent JSON.

The intended lesson is:

> **Measure protocol trade-offs in the actual workload; do not infer them from the technology name alone.**

---

## 10. Optional: inspect REST and gRPC on the wire with Docker/TShark

Postman shows readable logical request/response data. On the wire, however, the two Inventory adapters use different representations: REST exchanges JSON over HTTP, while gRPC transmits binary Protocol Buffer messages inside gRPC frames over HTTP/2.

The Compose file contains an optional `grpc-sniffer` service using the `parrotsec/tshark` image. It shares the network namespace of `inventory-service`, so no Wireshark/TShark installation is needed on the host. The capture filter is intentionally restricted to the two application adapter ports:

```text
50051  -> Inventory gRPC adapter
8081   -> Inventory REST adapter
```

Prometheus scrapes `/metrics` from the Checkout services on port `8000`; that traffic is outside this capture filter (and outside the Inventory network namespace), so it does not pollute the protocol comparison.

The sniffer listens on `eth0` rather than `any`. This keeps the capture focused on traffic entering/leaving the Inventory container through the Docker network and excludes the Inventory health check, which calls `http://localhost:8081/health` over the loopback interface every few seconds.

Start the application:

```bash
docker compose up --build -d
```

Then, in a second terminal:

```bash
docker compose --profile tools run --rm grpc-sniffer
```

or:

```bash
make sniff
```

Stop the capture with `Ctrl+C`. Because the command uses `docker compose run --rm`, the temporary TShark container is removed when it exits.

Now generate either kind of internal Inventory call:

```text
POST http://localhost:8000/checkouts  -> internal gRPC call to :50051
POST http://localhost:8001/checkouts  -> internal REST call to :8081
```

You can also invoke `CheckAvailability` directly from Postman against `localhost:50051`, or call the Inventory REST adapter directly on `http://localhost:8081/availability`.

The TShark capture filter is:

```text
tcp port 50051 or tcp port 8081
```

and its display filter shows HTTP/1.x messages for the REST adapter plus HTTP/2 DATA frames for gRPC. The hexadecimal dump (`-x`) remains enabled, so you can compare readable JSON traffic with binary gRPC/Protobuf payloads.

A gRPC message uses a 5-byte message prefix:

```text
+------------------+------------------------+----------------------+
| compression flag | message length         | protobuf payload     |
| 1 byte           | 4 bytes, big endian    | N bytes              |
+------------------+------------------------+----------------------+
```

Conceptually:

```text
Postman readable fields
        |
        v
Protocol Buffer serialization
        |
        v
binary protobuf payload
        |
        v
gRPC 5-byte message prefix
        |
        v
HTTP/2 DATA frame
```

This distinguishes three concepts:

```text
.proto contract       -> schema and RPC definition
Protocol Buffers      -> binary message serialization
gRPC over HTTP/2      -> remote-call framing and transport
```

> TShark is diagnostic tooling only; it is not part of either microservice architecture. It observes only traffic matching the adapter-port filter; Prometheus metric collection is not part of this capture.

---

## 11. Optional: run the Dockerized gRPC demo clients

The small programmatic gRPC examples also run inside Docker:

```bash
docker compose --profile tools run --rm grpc-client unary.py
```

```bash
docker compose --profile tools run --rm grpc-client server_streaming.py
```

```bash
docker compose --profile tools run --rm grpc-client client_streaming.py
```

```bash
docker compose --profile tools run --rm grpc-client bidirectional.py
```

They are useful after the Postman demonstration to show how generated stubs are consumed from code.

---

## 12. REST vs gRPC in this concrete example

| Concern | REST internal adapter | gRPC internal adapter |
|---|---|---|
| Checkout port | `InventoryGateway` | `InventoryGateway` |
| Checkout adapter | `RestInventoryClient` | `GrpcInventoryClient` |
| Inventory inbound port | `InventoryUseCases` | `InventoryUseCases` |
| Inventory adapter | `RestInventoryAdapter` | `GrpcInventoryAdapter` |
| Payload | JSON | Protocol Buffers |
| Transport | HTTP request/response | gRPC over HTTP/2 |
| Contract | OpenAPI generated by FastAPI | `.proto` |
| Client integration | generic HTTP client | generated typed stub |
| Unary request/response | Yes | Yes |
| Native gRPC streaming models | No | Yes |
| Serialized payload in this lab | measured | measured |
| Client-observed latency in this lab | measured | measured |

The experiment deliberately keeps the application cores stable while replacing adapters:

```text
                        Checkout core
                             |
                       InventoryGateway
                        /           \
                     REST           gRPC
                      |              |
                      +------v-------+
                         Inventory
                           core
```

That is the architectural lesson. The performance metrics are a measurable consequence of a transport choice, not the definition of the architecture itself.

---

## 13. Run the tests

Tests also run through Docker:

```bash
make test
```

or:

```bash
docker compose --profile tools run --rm test-runner
```

The tests exercise the application cores and verify that the Inventory REST adapter reaches the same `InventoryApplicationService` used by the gRPC path.

---

## 14. Stop the lab

```bash
docker compose down -v
```

---

## Teaching sequence

A useful classroom walkthrough is:

```text
1. Start from two different services: Checkout and Inventory
        |
        v
2. Inspect inventory.proto and the four gRPC interaction models
        |
        v
3. Explain Docker-time Protocol Buffer code generation
        |
        v
4. Optionally run make generate-grpc-skeleton and inspect InventoryServiceServicer
        |
        v
5. Compare the generated Servicer with GrpcInventoryAdapter and InventoryUseCases
        |
        v
6. Identify Checkout's InventoryGateway outbound port
        |
        v
7. Compare GrpcInventoryClient and RestInventoryClient
        |
        v
8. Identify InventoryUseCases inbound port
        |
        v
9. Compare GrpcInventoryAdapter and RestInventoryAdapter
        |
        v
10. docker compose up --build -d
        |
        v
11. Send the same POST /checkouts to :8000 and :8001
        |
        v
12. Observe: same cores, different internal transport
        |
        v
13. Use Postman for REST and direct gRPC exploration
        |
        v
14. Run make compare
        |
        v
15. Use Prometheus to compare latency + serialized payload bytes
        |
        v
16. Discuss why localhost latency is not a universal benchmark
        |
        v
17. Use TShark to inspect actual REST and gRPC traffic on the wire
        |
        v
18. Explore the three native streaming gRPC models
```

The most important end-to-end comparison is:

```text
REST client -> Checkout -> InventoryGateway -> GrpcInventoryClient
                                           -> gRPC -> GrpcInventoryAdapter

REST client -> Checkout -> InventoryGateway -> RestInventoryClient
                                           -> HTTP -> RestInventoryAdapter

both paths -> InventoryUseCases -> InventoryApplicationService
```

The lab therefore connects **Hexagonal Architecture**, **REST**, **gRPC**, **Protocol Buffers**, **OpenAPI**, **observability**, and **measurement** without coupling the application core to a specific transport technology.
