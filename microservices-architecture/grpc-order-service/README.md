# gRPC Service Integration: REST Checkout Outside, gRPC Inventory Inside

This lab demonstrates **gRPC service-to-service communication** with two different microservices and one realistic collaboration:

- an external **Checkout Service** exposes REST/JSON through FastAPI;
- Checkout needs stock information from a separate internal **Inventory Service**;
- Checkout calls Inventory through **gRPC**;
- the gRPC contract is defined once in `proto/inventory.proto`;
- `grpcio-tools` generates the client stub and server-side interface **inside the Docker images**;
- both services keep transport details outside their application cores through explicit ports and adapters;
- Inventory also has an explicit `InventoryRepository` outbound port, implemented in this lab by an **in-memory adapter** rather than a real database;
- the public REST flow demonstrates a **Unary gRPC** call internally;
- **Postman** can call the internal gRPC endpoint directly to visualize Unary, Server Streaming, Client Streaming, and Bidirectional Streaming;
- an optional **TShark container** can inspect the HTTP/2 frames and binary gRPC/Protocol Buffer payload without installing Wireshark on the host.

The main teaching point is that REST and gRPC solve different boundary needs and can naturally coexist in the same system.

> **Docker-first lab:** the classroom workflow does **not** require Python, `pip`, `protoc`, `grpcio-tools`, `grpcurl`, Wireshark, or TShark on the host machine. Docker builds the services, generates the Protocol Buffer Python code, and can run TShark in a diagnostic container. Postman Desktop is optional but recommended for graphical gRPC exploration.

---

## Architecture

```text
External client
      |
      | REST / JSON
      v
+------------------------------------------------------+
| Checkout Service                                     |
|                                                      |
| FastAPI REST adapter                                 |
|        |                                             |
|        v                                             |
| CheckoutUseCases              inbound port           |
|        ^                                             |
|        |                                             |
| CheckoutApplicationService    application core       |
|        |                                             |
|        v                                             |
| InventoryGateway              outbound port          |
|        ^                                             |
|        |                                             |
| GrpcInventoryClient           outbound gRPC adapter  |
+--------|---------------------------------------------+
         |
         | generated InventoryServiceStub
         | gRPC / HTTP/2 / Protocol Buffers
         v
+------------------------------------------------------+
| Inventory Service                                    |
|                                                      |
| GrpcInventoryAdapter          inbound gRPC adapter   |
|        |                                             |
|        v                                             |
| InventoryUseCases             inbound port           |
|        ^                                             |
|        |                                             |
| InventoryApplicationService   application core       |
|        |                                             |
|        v                                             |
| InventoryRepository           outbound port          |
|        ^                                             |
|        |                                             |
| InMemoryInventoryRepository   outbound adapter       |
+------------------------------------------------------+
```

This is intentionally **not** a REST proxy in front of the same service. Checkout and Inventory have different responsibilities:

- **Checkout Service** handles the external checkout use case;
- **Inventory Service** owns stock availability and stock operations.

This makes the service-to-service role of gRPC explicit.

### Persistence scope: why Inventory uses an in-memory repository

The Inventory Service has a real **outbound port** and a real **outbound adapter**, but it intentionally does **not** use a real database in this lab:

```text
InventoryApplicationService
        |
        v
InventoryRepository            outbound port
        ^
        |
InMemoryInventoryRepository    outbound adapter
```

So the distinction is:

| Element | Present in this lab? |
|---|---|
| `InventoryRepository` outbound port | Yes |
| Concrete repository adapter | Yes |
| Real database such as PostgreSQL | No |
| Persistent storage across restarts | No |

This is an intentional teaching choice. **Persistence is not the focus of this example**; the lab concentrates on the gRPC contract, generated stubs, service-to-service communication, Hexagonal Architecture boundaries, and the four RPC interaction models.

The previous Hexagonal Architecture lab already demonstrates a real PostgreSQL persistence adapter. If this Inventory Service later needed durable storage, `InMemoryInventoryRepository` could be replaced by an adapter such as `PostgresInventoryRepository` without changing `InventoryApplicationService`, because the application core depends only on `InventoryRepository`.

```text
Current lab                           Possible extension

InventoryRepository                  InventoryRepository
        ^                                     ^
        |                                     |
InMemoryInventoryRepository          PostgresInventoryRepository
                                              |
                                              v
                                          PostgreSQL
```

> **Teaching point:** the in-memory repository is not a shortcut around Hexagonal Architecture. It is one concrete outbound adapter behind the same repository port; only the persistence technology has been simplified to keep the gRPC concepts visible.

---

## Prerequisites

For the main lab you only need:

- **Docker** with Docker Compose;
- **Postman Desktop** if you want the graphical gRPC demonstration.

You do **not** need a local Python environment or Wireshark/TShark installation for the classroom workflow. Packet inspection is performed by an optional Docker container.

### Install Postman Desktop

Official download page:

- <https://www.postman.com/downloads/>

Common installation options:

**macOS**

```bash
brew install --cask postman
```

**Linux**

```bash
sudo snap install postman
```

**Windows**

Download and run the installer from the official Postman download page.

For this lab, the **desktop app** is preferable because the gRPC service runs locally on `localhost:50051`.

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
│   │   └── adapters/
│   │       ├── inbound/rest/
│   │       └── outbound/grpc/
│   ├── Dockerfile
│   └── requirements.txt
├── inventory-service/
│   ├── src/inventory_service/
│   │   ├── domain/
│   │   ├── application/
│   │   │   ├── ports/
│   │   │   └── services/
│   │   └── adapters/
│   │       ├── inbound/grpc/
│   │       └── outbound/memory/
│   ├── Dockerfile
│   └── requirements.txt
├── demo-clients/
│   ├── unary.py
│   ├── server_streaming.py
│   ├── client_streaming.py
│   └── bidirectional.py
├── tests/
├── docker-compose.yml
└── Makefile
```

Generated Protocol Buffer Python files are created during Docker image builds and are not part of the application core.

---

## 1. Start from the `.proto` contract

`proto/inventory.proto` is the source of truth for the internal Inventory API.

```proto
service InventoryService {
  rpc CheckAvailability(CheckAvailabilityRequest) returns (AvailabilityReply);
  rpc WatchStock(WatchStockRequest) returns (stream StockUpdate);
  rpc CheckMany(stream CheckAvailabilityRequest) returns (BatchAvailabilityReply);
  rpc InventorySession(stream InventoryCommand) returns (stream InventoryEvent);
}
```

The same service contract demonstrates all four gRPC interaction models:

| Interaction model | RPC | Shape |
|---|---|---|
| Unary | `CheckAvailability` | one request → one response |
| Server Streaming | `WatchStock` | one request → many responses |
| Client Streaming | `CheckMany` | many requests → one response |
| Bidirectional Streaming | `InventorySession` | many requests ↔ many responses |

### Anatomy of a Protocol Buffer definition

A unary operation is defined by a service, an RPC, and request/response messages:

```proto
service InventoryService {
  rpc CheckAvailability(CheckAvailabilityRequest) returns (AvailabilityReply);
}

message CheckAvailabilityRequest {
  string sku = 1;
  int32 quantity = 2;
}
```

Read it as follows:

- `service InventoryService` declares the remotely accessible service;
- `rpc CheckAvailability(...) returns (...)` declares one remote operation;
- `message` declares the data exchanged between client and server;
- `string` and `int32` make fields strongly typed;
- `= 1` and `= 2` are stable numeric field tags used on the wire;
- `stream` before a request or response type changes the interaction model.

For compatible schema evolution, new fields should use new numeric tags and removed field numbers should not be reused.

---

## 2. Code generation happens inside Docker

There is **no required host-side code-generation step**.

Both service Dockerfiles compile `proto/inventory.proto` while the images are built:

```text
inventory.proto
      |
      | grpc_tools.protoc inside Docker build
      v
+-------------------------+
| inventory_pb2.py        |  Protocol Buffer messages
| inventory_pb2_grpc.py   |  client stub + server interface
+-------------------------+
```

Conceptually, the compiler executes:

```bash
python -m grpc_tools.protoc \
  -I/app/proto \
  --python_out=/app/generated \
  --grpc_python_out=/app/generated \
  /app/proto/inventory.proto
```

The important point is **what is generated**, not where the command is run:

- `inventory_pb2.py` contains Protocol Buffer message classes and serialization support;
- `inventory_pb2_grpc.py` contains the generated client stub and server-side gRPC interface.

Generated files are **transport plumbing**. Business logic must not be added to them because they can be regenerated at any time.

> The generated gRPC classes are not domain models and are not application ports.

---

## 3. Understand the two sides of the gRPC boundary

This section is conceptual: **there is nothing to execute here**.

A gRPC call has a client side and a server side. In Hexagonal Architecture they play different adapter roles.

### Checkout: gRPC is an outbound adapter

Checkout needs Inventory, but its application core should not depend on gRPC:

```text
CheckoutApplicationService
          |
          v
   InventoryGateway             outbound port
          ^
          |
   GrpcInventoryClient          outbound adapter
          |
          v
InventoryServiceStub            generated client
```

The application core depends on an application-defined abstraction:

```python
class InventoryGateway(ABC):
    @abstractmethod
    def check_availability(self, sku: str, quantity: int) -> InventoryAvailability:
        ...
```

The gRPC-specific adapter implements it:

```python
class GrpcInventoryClient(InventoryGateway):
    ...
```

**The generated gRPC stub is not the application port.** `InventoryGateway` is the outbound port; `GrpcInventoryClient` is the adapter that uses the generated stub.

### Inventory: gRPC is an inbound adapter

On the server side:

```text
InventoryServiceServicer        generated server interface
          |
          v
GrpcInventoryAdapter            inbound adapter
          |
          v
InventoryUseCases               inbound port
          ^
          |
InventoryApplicationService     application core
```

The gRPC adapter invokes `InventoryUseCases`. The application service implements that inbound port.

Therefore the same gRPC connection is viewed differently by the two services:

```text
Checkout Service                       Inventory Service

InventoryGateway                       InventoryUseCases
      ^                                      ^
      |                                      |
GrpcInventoryClient   -- gRPC -->   GrpcInventoryAdapter
   outbound adapter                     inbound adapter
```

---

## 4. DTOs vs domain models

Transport objects stay at the transport boundary.

### REST boundary

FastAPI uses **Pydantic** models to represent and validate HTTP request/response data.

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
CheckoutUseCases
```

Pydantic models belong to the **REST adapter**. They are not domain entities and are not part of the application core.

### gRPC boundary

At the gRPC boundary, generated **Protocol Buffer message classes** play a similar transport-level role:

```text
gRPC / Protobuf
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

The gRPC adapters translate between generated Protobuf messages and application/domain objects. The application core should not depend on generated transport types.

```text
Pydantic models       -> REST transport DTOs
Protobuf messages     -> gRPC transport DTOs
Domain objects/ports  -> application and domain layers
```

---

## 5. Run the two services

Start the stack:

```bash
docker compose up --build -d
```

Check it:

```bash
docker compose ps
```

Available endpoints:

| Component | Address |
|---|---|
| Checkout REST API | `http://localhost:8000` |
| FastAPI / Swagger UI | `http://localhost:8000/docs` |
| Inventory gRPC API | `localhost:50051` |

Port `50051` is exposed to the host **only for this lab**, so that Postman can call the internal gRPC service directly. In a real deployment the Inventory gRPC endpoint could remain private to the service network.

---

## 6. Main demo: REST outside, Unary gRPC inside

The normal external consumer calls Checkout through REST.

```bash
curl -X POST http://localhost:8000/checkouts \
  -H 'Content-Type: application/json' \
  -d '{"sku":"pizza","quantity":2}'
```

Example response:

```json
{
  "sku": "pizza",
  "quantity": 2,
  "availableQuantity": 8,
  "status": "ACCEPTED"
}
```

The important part is the internal collaboration:

```text
External client
      |
      | POST /checkouts + JSON
      v
FastAPI REST adapter
      |
      v
CheckoutUseCases
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
      | Unary RPC: CheckAvailability(...)
      | HTTP/2 + Protocol Buffers
      v
GrpcInventoryAdapter
      |
      v
InventoryUseCases
      |
      v
InventoryApplicationService
```

This is the main integration scenario:

```text
REST external boundary
        |
        v
Checkout Service
        |
        | Unary gRPC
        v
Inventory Service
```

The external client does not need to know that gRPC is used internally.

---

## 7. Test the REST API graphically with Postman

The same Postman Desktop application can also be used as a normal HTTP client for the public Checkout REST API.

This is useful in class because students can compare the **external REST boundary** and the **internal gRPC boundary** using the same graphical tool.

### 7.1 Create a REST request

With the Docker stack running, open Postman and create a new **HTTP** request.

Set:

```text
Method: POST
URL:    http://localhost:8000/checkouts
```

In **Headers**, use:

```text
Content-Type: application/json
```

In **Body → raw → JSON**, enter:

```json
{
  "sku": "pizza",
  "quantity": 2
}
```

Click **Send**.

The Checkout Service should return `201 Created` with a response similar to:

```json
{
  "sku": "pizza",
  "quantity": 2,
  "availableQuantity": 8,
  "status": "ACCEPTED"
}
```

The interesting part is that this REST request triggers a **Unary gRPC call** internally:

```text
Postman HTTP request
        |
        | POST /checkouts + JSON
        v
Checkout REST adapter
        |
        v
CheckoutApplicationService
        |
        v
GrpcInventoryClient
        |
        | CheckAvailability(...)
        v
Inventory gRPC Service
```

So Postman can be used in two different modes in the same lab:

```text
Postman HTTP request
    -> public REST API
    -> http://localhost:8000/checkouts

Postman gRPC request
    -> internal gRPC API
    -> localhost:50051
```

### 7.2 Optional health check

You can also call:

```text
GET http://localhost:8000/health
```

Expected response:

```json
{
  "status": "ok"
}
```

This checks only the Checkout REST service. The `POST /checkouts` request is the more interesting demonstration because it exercises the complete **REST → Checkout → gRPC → Inventory** collaboration.

---

## 8. Explore gRPC graphically with Postman

Postman is useful here because it lets you invoke the internal Inventory API directly and visualize the four gRPC interaction models without writing or running a client manually.

### 8.1 Connect to the Inventory Service

With the Docker stack running:

1. Open **Postman Desktop**.
2. Select **New → gRPC**.
3. Enter the server URL:

```text
localhost:50051
```

4. Leave **TLS disabled** for this local lab.
5. Select a method from `ftgo.inventory.v1.InventoryService`.

The Inventory Service enables **gRPC server reflection**, so Postman should discover the service definition automatically.

If needed, you can instead import:

```text
proto/inventory.proto
```

from the **Service definition** section.

### 8.2 Unary — `CheckAvailability`

Select:

```text
ftgo.inventory.v1.InventoryService / CheckAvailability
```

Message:

```json
{
  "sku": "pizza",
  "quantity": 2
}
```

Click **Invoke**.

Conceptually:

```text
request  -------------------->
         CheckAvailability
response <--------------------
```

This is the same gRPC interaction that Checkout uses internally during the REST demo.

### 8.3 Server Streaming — `WatchStock`

Select:

```text
ftgo.inventory.v1.InventoryService / WatchStock
```

Message:

```json
{
  "sku": "pizza"
}
```

Click **Invoke**.

One request produces multiple server messages:

```text
request  -------------------->
response <-------------------- stock update 1
response <-------------------- stock update 2
response <-------------------- stock update 3
```

Postman displays the received messages as a stream/timeline.

### 8.4 Client Streaming — `CheckMany`

Select:

```text
ftgo.inventory.v1.InventoryService / CheckMany
```

Click **Invoke** to open the stream, then send several messages using **Send**:

```json
{
  "sku": "pizza",
  "quantity": 2
}
```

```json
{
  "sku": "pasta",
  "quantity": 5
}
```

```json
{
  "sku": "salad",
  "quantity": 1
}
```

Then click **End Streaming**.

The server returns one final `BatchAvailabilityReply`.

```text
request  -------------------->
request  -------------------->
request  -------------------->
         end stream
response <-------------------- one batch reply
```

### 8.5 Bidirectional Streaming — `InventorySession`

Select:

```text
ftgo.inventory.v1.InventoryService / InventorySession
```

Click **Invoke**, then send messages such as:

```json
{
  "sku": "pizza",
  "action": "check",
  "quantity": 1
}
```

```json
{
  "sku": "pizza",
  "action": "reserve",
  "quantity": 2
}
```

```json
{
  "sku": "pizza",
  "action": "release",
  "quantity": 1
}
```

The client can keep sending commands while the server emits events on the same open session.

```text
command  -------------------->
         <-------------------- event
command  -------------------->
         <-------------------- event
command  -------------------->
         <-------------------- event
```

Click **End Streaming** when finished.

### Why only Unary is demonstrated through the external REST API

The public REST endpoint maps naturally to a synchronous request/response interaction, so it demonstrates **Unary gRPC** internally.

The other three gRPC interaction models are tested directly against Inventory because mapping them to a traditional REST endpoint would require additional mechanisms such as SSE, chunked streaming, or WebSockets and would distract from the gRPC lesson.

```text
External REST demo
    -> Unary gRPC internally

Direct Postman gRPC demo
    -> Unary
    -> Server Streaming
    -> Client Streaming
    -> Bidirectional Streaming
```

---

## 9. Optional: inspect gRPC on the wire with Docker/TShark

Postman shows the logical request and response in a readable form, but gRPC actually sends **binary Protocol Buffer messages inside gRPC frames over HTTP/2**.

For this lab you can observe that traffic without installing Wireshark. The Compose file contains an optional `grpc-sniffer` service based on the `wireshark/tshark` image.

The sniffer shares the **network namespace of `inventory-service`**, so it sees the traffic arriving on gRPC port `50051`:

```text
Postman
   |
   | gRPC / HTTP/2
   v
localhost:50051
   |
   v
Inventory Service
   ^
   |
TShark container
(shared network namespace)
```

Start the application first:

```bash
docker compose up --build -d
```

Then, in a second terminal, start the sniffer:

```bash
docker compose --profile tools run --rm grpc-sniffer
```

or equivalently:

```bash
make sniff
```

Now invoke an Inventory RPC from Postman, for example `CheckAvailability`.

The TShark output is intentionally verbose and includes:

- HTTP/2 `DATA` frames;
- the gRPC message envelope;
- a hexadecimal dump of the binary payload.

The Compose command decodes TCP port `50051` as HTTP/2 and filters the display to HTTP/2 `DATA` frames:

```text
-i any
-f "tcp port 50051"
-d tcp.port==50051,http2
-Y "http2.type == 0"
-V
-x
```

A gRPC message carried in an HTTP/2 `DATA` frame begins with a **5-byte gRPC message prefix**:

```text
+------------------+------------------------+----------------------+
| compression flag | message length         | protobuf payload     |
| 1 byte           | 4 bytes, big endian    | N bytes              |
+------------------+------------------------+----------------------+
```

Conceptually:

```text
Postman view
{
  "sku": "pizza",
  "quantity": 2
}
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

This is useful for distinguishing three different concepts that are often conflated:

```text
.proto contract       -> schema and RPC definition
Protocol Buffers      -> binary message serialization
gRPC over HTTP/2      -> remote-call framing and transport
```

> **Important:** the sniffer is a diagnostic teaching tool, not an application component. It is placed under the Compose `tools` profile and is not started by the normal `docker compose up` workflow.

Stop the sniffer with `Ctrl+C` when the demonstration is complete.

---

## 10. Optional: run the Dockerized gRPC demo clients

Postman is the recommended graphical demonstration. The repository also contains small Python gRPC clients, but they run **inside Docker**, not on the host.

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

These scripts are useful for showing that generated stubs can also be consumed programmatically.

---

## 11. REST vs gRPC in this concrete example

| Concern | External Checkout boundary | Internal Inventory boundary |
|---|---|---|
| Technology | REST/HTTP | gRPC over HTTP/2 |
| Payload | JSON | Protocol Buffers |
| Main abstraction | Resources + HTTP operations | Typed remote operations |
| Consumer | Browsers / generic HTTP clients | Controlled internal services |
| Client code | Any HTTP client | Generated typed stub |
| Contract | FastAPI/OpenAPI | `.proto` |
| Interaction model | Mainly request/response here | Unary + native streaming RPCs |
| Main benefit here | Openness and interoperability | Strong contract and rich service-to-service interactions |

The lesson is **not** that gRPC is always better than REST. The appropriate choice depends on the communication boundary.

A common architecture is:

```text
external heterogeneous clients
            |
           REST
            v
      public service
            |
           gRPC
            v
      internal service
```

---

## 12. Stop the lab

```bash
docker compose down -v
```

---

## Teaching sequence

A useful classroom walkthrough is:

```text
1. Why two different services?
        |
        v
2. Inspect inventory.proto
        |
        v
3. Understand generated stub + server interface
   (generation happens during Docker build)
        |
        v
4. Understand Checkout outbound port + gRPC adapter
        |
        v
5. Understand Inventory gRPC adapter + inbound port
        |
        v
6. docker compose up --build -d
        |
        v
7. REST call to Checkout with curl or Postman HTTP
        |
        v
8. Observe Unary gRPC collaboration internally
        |
        v
9. In Postman, compare HTTP and gRPC requests
        |
        v
10. Open Postman gRPC on localhost:50051
        |
        v
11. Explore Unary + three streaming models
        |
        v
12. Optionally run the Docker/TShark sniffer
    and inspect HTTP/2 DATA + binary gRPC payload
        |
        v
13. Compare REST and gRPC boundary trade-offs
```

The most important end-to-end observation is:

```text
REST client
    -> Checkout Service
    -> InventoryGateway
    -> GrpcInventoryClient
    -> gRPC
    -> GrpcInventoryAdapter
    -> InventoryUseCases
```

The external contract and the internal collaboration use different technologies because they serve different consumers and architectural needs.
