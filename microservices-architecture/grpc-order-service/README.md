# gRPC Order Service: REST Outside, gRPC Inside

This example demonstrates the gRPC concepts used in the **Microservices Architecture** lectures with one small FTGO-inspired scenario:

- an **external API service** exposes REST/JSON to web and heterogeneous clients;
- the API service calls an **internal Order Service** through gRPC;
- the gRPC contract is defined once in `proto/order.proto`;
- `grpcio-tools` generates client/server plumbing from that contract;
- the internal service uses a small **Hexagonal Architecture**: the gRPC layer is an inbound adapter that invokes application use cases;
- four small clients demonstrate **Unary**, **Server Streaming**, **Client Streaming**, and **Bidirectional Streaming** RPCs.

The goal is to show why REST and gRPC are often **complementary**, not competing choices.

## Architecture

```text
External client
      |
      | REST / JSON
      v
+-----------------------+
| Public API Service    |
| FastAPI               |
|                       |
| generated gRPC client |
+-----------+-----------+
            |
            | gRPC / HTTP/2
            | Protocol Buffers
            v
+---------------------------------------+
| Internal Order Service                |
|                                       |
| gRPC adapter (generated interface)    |
|             |                         |
|             v                         |
|       OrderUseCases                   |
|       (inbound port)                  |
|             |                         |
|             v                         |
|   OrderApplicationService             |
|       (application core)              |
|             |                         |
|             v                         |
|       OrderRepository                 |
|       (outbound port)                 |
|             |                         |
|             v                         |
|   InMemoryOrderRepository             |
+---------------------------------------+
```

The public service intentionally uses **REST** because it is easy to consume from browsers and generic clients. The internal service uses **gRPC** because both sides are controlled services and can benefit from a strong contract, generated code, compact messages, HTTP/2, and streaming.

## Repository layout

```text
grpc-order-service/
├── proto/
│   └── order.proto
├── api-service/
│   ├── app/main.py
│   ├── Dockerfile
│   └── requirements.txt
├── order-service/
│   ├── app/
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
│   ├── bidirectional.py
│   └── rest_client.py
├── scripts/generate_proto.sh
├── tests/
├── docker-compose.yml
└── Makefile
```

## 1. Start from the `.proto` contract

`proto/order.proto` is the source of truth for the internal API.

```proto
service OrderService {
  rpc CreateOrder(CreateOrderRequest) returns (OrderReply);
  rpc WatchOrder(WatchOrderRequest) returns (stream OrderUpdate);
  rpc BulkCreateOrders(stream CreateOrderRequest) returns (BulkCreateReply);
  rpc OrderConversation(stream OrderCommand) returns (stream OrderEvent);
}
```

It also defines the exchanged messages and their stable numeric tags:

```proto
message CreateOrderRequest {
  string restaurant_id = 1;
  string item = 2;
  int32 quantity = 3;
}
```

The field numbers (`1`, `2`, `3`) are part of the wire contract. When evolving the schema, new fields should use new numbers and removed numbers should not be reused.

### Anatomy of a Protocol Buffer definition

A minimal unary RPC combines a **service**, an **RPC operation**, and the request/response **message types**:

```proto
service OrderService {
  rpc CreateOrder(CreateOrderRequest) returns (OrderReply);
}

message CreateOrderRequest {
  string restaurant_id = 1;
  string item = 2;
  int32 quantity = 3;
}
```

Read it from the outside in:

- `service OrderService` declares the remotely accessible service.
- `rpc CreateOrder(...) returns (...)` declares one remote operation and its input/output types.
- `message` declares the serialized data exchanged between client and server.
- `string`, `int32`, and the other scalar types make the contract strongly typed.
- `= 1`, `= 2`, `= 3` are stable field numbers used on the wire; they identify fields independently of their names.
- `stream` placed before a request or response type changes the RPC interaction model from unary to client, server, or bidirectional streaming.

For example:

```proto
rpc WatchOrder(WatchOrderRequest) returns (stream OrderUpdate);
```

means **one request -> a stream of responses**, while:

```proto
rpc OrderConversation(stream OrderCommand) returns (stream OrderEvent);
```

means **bidirectional streaming**.

## 2. Generate the Python gRPC code

Install the tools locally if you want to inspect generated code without Docker:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
./scripts/generate_proto.sh
```

The command behind the script is:

```bash
python -m grpc_tools.protoc \
  -I proto \
  --python_out=generated \
  --grpc_python_out=generated \
  proto/order.proto
```

### Understanding the generation command

Read the command as a small compilation pipeline:

- `python -m grpc_tools.protoc` runs the Protocol Buffer compiler distributed with `grpcio-tools`.
- `-I proto` adds `proto/` to the import search path for `.proto` files.
- `--python_out=generated` generates Python classes for Protocol Buffer **messages**.
- `--grpc_python_out=generated` generates the gRPC **client stub** and **server-side service interface**.
- `proto/order.proto` is the input contract.

Conceptually:

```text
order.proto
    |
    +--> order_pb2.py       message classes / serialization
    |
    +--> order_pb2_grpc.py  client stub + server interface
```

This generates:

```text
order_pb2.py       # Protocol Buffer message classes
order_pb2_grpc.py  # client stub + server-side service interface
```

Do **not** put business logic in the generated files. They can be regenerated at any time.

## 3. Run the two services

```bash
docker compose up --build -d
```

Check them:

```bash
docker compose ps
```

The endpoints are:

- REST API: `http://localhost:8000`
- FastAPI/Swagger UI: `http://localhost:8000/docs`
- internal gRPC service: `localhost:50051`

## 4. REST outside, gRPC inside

Create an order through the **public REST API**:

```bash
curl -X POST http://localhost:8000/orders \
  -H 'Content-Type: application/json' \
  -d '{"restaurant_id":"rest-1","item":"pizza","quantity":2}'
```

Flow:

```text
curl
  -> HTTP/JSON
  -> FastAPI
  -> generated OrderServiceStub
  -> gRPC / HTTP/2 / Protocol Buffers
  -> GrpcOrderAdapter
  -> OrderApplicationService
```

The FastAPI service is therefore both:

- a **REST server** for external clients;
- a **gRPC client** of the internal Order Service.

This makes the REST/gRPC trade-off concrete in one example.

## 5. Hexagonal mapping of the internal service

The generated gRPC base class is implemented by:

```text
order-service/app/adapters/inbound/grpc/server.py
```

`GrpcOrderAdapter` translates Protocol Buffer messages into calls to the application core:

```text
GrpcOrderAdapter
       |
       v
OrderUseCases          inbound port
       ^
       |
OrderApplicationService
       |
       v
OrderRepository        outbound port
       ^
       |
InMemoryOrderRepository
```

The application service knows nothing about gRPC, HTTP/2, Protocol Buffers, or FastAPI.

## 6. Four gRPC interaction models

The examples below call the **internal service directly** so the interaction pattern is easy to observe.

### Unary: 1 request -> 1 response

```bash
make unary
```

RPC:

```proto
rpc CreateOrder(CreateOrderRequest) returns (OrderReply);
```

Use it when a normal synchronous request/response is sufficient.

### Server Streaming: 1 request -> N responses

```bash
make server-stream
```

RPC:

```proto
rpc WatchOrder(WatchOrderRequest) returns (stream OrderUpdate);
```

The example streams order status changes:

```text
CREATED
ACCEPTED
PREPARING
READY
```

The REST API also demonstrates how a public service can bridge this stream through:

```text
GET /orders/{orderId}/updates
```

### Client Streaming: N requests -> 1 response

```bash
make client-stream
```

RPC:

```proto
rpc BulkCreateOrders(stream CreateOrderRequest) returns (BulkCreateReply);
```

The client streams multiple orders and receives one final summary.

### Bidirectional Streaming: N requests <-> N responses

```bash
make bidi
```

RPC:

```proto
rpc OrderConversation(stream OrderCommand) returns (stream OrderEvent);
```

The client and server can independently exchange messages on the same HTTP/2 stream.

## 7. REST vs gRPC in this example

| Concern | External REST API | Internal gRPC API |
|---|---|---|
| Style | Resources + HTTP methods | Remote service operations |
| Contract | OpenAPI generated by FastAPI | `.proto` |
| Payload | JSON text | Protocol Buffers binary |
| Client | Browser / curl / generic HTTP | Generated typed stub |
| Transport | HTTP | HTTP/2 |
| Streaming | Requires HTTP-specific mechanisms | Native server/client/bidirectional streaming |
| Best fit here | External heterogeneous clients | Controlled service-to-service communication |

The important point is not that one protocol is universally better. The communication boundary determines the best trade-off.

## 8. Optional: inspect the gRPC API with reflection

The server enables gRPC reflection, so a tool such as `grpcurl` can inspect the service:

```bash
grpcurl -plaintext localhost:50051 list
grpcurl -plaintext localhost:50051 describe ftgo.order.v1.OrderService
```

Example unary call:

```bash
grpcurl -plaintext \
  -d '{"restaurantId":"rest-1","item":"pizza","quantity":2}' \
  localhost:50051 \
  ftgo.order.v1.OrderService/CreateOrder
```

## 9. Test the application core without gRPC

The core can be tested independently of transport technology:

```bash
pytest -q
```

`tests/test_order_application_service.py` uses the in-memory repository directly and never starts a gRPC server.

This is one of the main benefits of Ports and Adapters: replacing REST with gRPC, or adding both, does not require moving the business logic into the transport layer.

## Cleanup

```bash
docker compose down -v
```

## What to observe

1. `order.proto` is the contract used by both sides of the internal call.
2. `grpcio-tools` generates transport plumbing, not application behavior.
3. FastAPI exposes a REST-friendly boundary while internally using a generated gRPC stub.
4. The gRPC server is an inbound adapter around the application core.
5. The four RPC styles are differences in the communication model, not changes to the domain model.
6. REST and gRPC can coexist naturally in the same microservice system.
