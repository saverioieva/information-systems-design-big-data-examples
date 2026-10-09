# Hexagonal Order Service — synchronous REST RPI

This lab implements a small **Order Service** and uses one concrete example to connect several concepts from the Microservices Architecture module:

- synchronous **Remote Procedure Invocation (RPI)** over HTTP;
- **Hexagonal Architecture** with explicit inbound/outbound ports and adapters;
- **FastAPI** as the inbound REST adapter;
- **PostgreSQL** as the outbound persistence adapter;
- **OpenAPI** as the published API contract;
- **Swagger UI** for interactive documentation;
- **Swagger Codegen** for generating a client from the contract;
- **Docker Compose** for running the complete example locally.

The example intentionally contains only one table and two operations so that the architectural boundaries remain visible.

## Architecture

```text
                         Order Service

 Client
   |
   | HTTP / REST
   v
+--------------------------- service boundary ---------------------------+
|                                                                         |
|  [REST adapter] ---> (OrderUseCases inbound port)                       |
|                              |                                          |
|                              v                                          |
|                   +-----------------------+                             |
|                   |  Application Core     |                             |
|                   | OrderApplicationService|                            |
|                   +-----------+-----------+                             |
|                               |                                         |
|                               v                                         |
|                    (OrderRepository outbound port)                      |
|                               |                                         |
|                               v                                         |
|                    [PostgreSQL repository adapter]                      |
+-------------------------------|-----------------------------------------+
                                v
                            PostgreSQL
                            orders table
```

The dependency direction is **outside → inside**:

- the REST adapter depends on the inbound port;
- `OrderApplicationService` implements the inbound port;
- the application core has no dependency on FastAPI, HTTP, SQLAlchemy, or PostgreSQL;
- the application core depends on the `OrderRepository` outbound port;
- the PostgreSQL adapter implements the outbound port;
- `main.py` is the composition root where concrete adapters are wired to the core.

> **Important:** an inbound REST adapter does **not** implement the inbound port. It translates HTTP into calls to that port. The application service implements the inbound port. An outbound adapter, instead, implements the outbound port required by the core.

## Project structure

```text
hexagonal_rpi_order_service/
├── openapi/
│   └── order-api.yaml
├── app/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── src/order_service/
│       ├── domain/
│       │   └── order.py
│       ├── application/
│       │   ├── ports/
│       │   │   ├── inbound/
│       │   │   │   └── order_use_cases.py
│       │   │   └── outbound/
│       │   │       └── order_repository.py
│       │   └── services/
│       │       └── order_service.py
│       ├── adapters/
│       │   ├── inbound/rest/
│       │   │   └── routes.py
│       │   └── outbound/postgres/
│       │       ├── models.py
│       │       └── repository.py
│       ├── infrastructure/
│       │   └── database.py
│       └── main.py
├── client/
│   └── rpi_client.py
├── tests/
│   └── test_order_service.py
├── scripts/
│   ├── generate-swagger-client.sh
│   └── generate-openapi-client.sh
└── docker-compose.yml
```

## 1. OpenAPI contract

The published contract is [`openapi/order-api.yaml`](openapi/order-api.yaml).

It exposes only two operations:

```text
POST /orders
GET  /orders/{orderId}
```

The REST boundary uses JSON such as:

```json
{
  "restaurantId": 42,
  "total": 25.50
}
```

The contract is intentionally independent from the Python implementation. It is used by Swagger UI and by the client-generation tools.

## 2. Run the complete example

From this directory:

```bash
docker compose up --build
```

Services:

| Component | URL |
|---|---|
| Order Service | http://localhost:8000 |
| FastAPI Swagger UI | http://localhost:8000/docs |
| Swagger UI rendering `order-api.yaml` | http://localhost:8080 |
| PostgreSQL | `localhost:5432` |

The two Swagger UIs have a useful teaching purpose:

- `:8000/docs` shows the OpenAPI document generated from the running FastAPI adapter;
- `:8080` shows the **explicit contract file** stored in the repository.

## 3. Follow one synchronous RPI call

Create an order:

```bash
curl -i -X POST http://localhost:8000/orders \
  -H 'Content-Type: application/json' \
  -d '{"restaurantId":42,"total":25.50}'
```

Example response:

```json
{
  "id": 1,
  "restaurantId": 42,
  "status": "CREATED",
  "total": 25.50
}
```

Retrieve it:

```bash
curl -i http://localhost:8000/orders/1
```

The execution path is:

```text
HTTP request
   ↓
FastAPI REST adapter
   ↓
OrderUseCases                  inbound port
   ↓
OrderApplicationService       application core
   ↓
OrderRepository               outbound port
   ↓
PostgresOrderRepository       outbound adapter
   ↓
PostgreSQL
```

Because this is synchronous RPI, the caller waits until the service returns the HTTP response.

## 4. Inspect PostgreSQL

The example persists orders in exactly one table:

```bash
docker compose exec postgres \
  psql -U orders -d orders -c '\\d orders'
```

Inspect the rows:

```bash
docker compose exec postgres \
  psql -U orders -d orders -c 'SELECT * FROM orders ORDER BY id;'
```

The SQLAlchemy mapping is an adapter detail. The domain `Order` object does not depend on SQLAlchemy.

## 5. Understand the Hexagonal components

| Hexagonal element | Implementation | Responsibility |
|---|---|---|
| Domain model | `domain/order.py` | Technology-independent `Order` entity |
| Inbound port | `application/ports/inbound/order_use_cases.py` | Operations offered by the application core |
| Application core | `application/services/order_service.py` | Implements the use cases and business rules |
| Inbound adapter | `adapters/inbound/rest/routes.py` | Translates HTTP/JSON to inbound-port calls |
| Outbound port | `application/ports/outbound/order_repository.py` | Persistence abstraction required by the core |
| Outbound adapter | `adapters/outbound/postgres/repository.py` | Implements the repository using PostgreSQL |
| Composition root | `main.py` | Connects concrete adapters to ports |

### Inbound side

The REST adapter receives HTTP-specific data:

```python
def create_order(request: CreateOrderRequest) -> OrderResponse:
    order = use_cases.create_order(request.restaurantId, request.total)
    return OrderResponse.from_domain(order)
```

Notice that `use_cases` has type `OrderUseCases`. The adapter knows the port, not the concrete application service.

### Application core

```python
class OrderApplicationService(OrderUseCases):
    def __init__(self, repository: OrderRepository) -> None:
        self._repository = repository
```

The core implements the inbound port and depends only on the outbound repository port.

### Outbound side

```python
class PostgresOrderRepository(OrderRepository):
    ...
```

PostgreSQL is replaceable because it lives behind `OrderRepository`.

## 6. Test the core without FastAPI or PostgreSQL

The test uses a tiny in-memory repository adapter:

```bash
docker compose run --rm order-service \
  pytest -q /app/tests
```

For local execution outside Docker, install the application requirements and set `PYTHONPATH=app/src` before running `pytest`.

The important observation is that `OrderApplicationService` can be tested without HTTP and without a database. This is one of the main benefits of ports and adapters.

## 7. Swagger UI

Open:

```text
http://localhost:8080
```

Swagger UI reads `openapi/order-api.yaml` directly. Use **Try it out** to inspect the operations described by the contract.

FastAPI also exposes its automatically generated Swagger UI at:

```text
http://localhost:8000/docs
```

Comparing the two is a useful exercise: the implementation should remain aligned with the published contract.

## 8. Generate a client with Swagger Codegen

The repository includes a Docker-based script, so Swagger Codegen does not need to be installed locally:

```bash
chmod +x scripts/generate-swagger-client.sh
./scripts/generate-swagger-client.sh
```

Generated code is written to:

```text
generated/swagger-python-client/
```

The flow is:

```text
order-api.yaml
      ↓
Swagger Codegen
      ↓
Python client / models
      ↓
synchronous REST call
      ↓
Order Service
```

An OpenAPI Generator script is also included as a modern alternative:

```bash
./scripts/generate-openapi-client.sh
```

## 9. Simple RPI client

For comparison with generated code, [`client/rpi_client.py`](client/rpi_client.py) is a minimal handwritten client-side REST adapter.

Run it after starting the stack:

```bash
python -m pip install requests
python client/rpi_client.py
```

It performs a `POST /orders`, waits for the result, and then performs `GET /orders/{id}`.

## 10. Stop and clean up

```bash
docker compose down -v
```

## Teaching sequence

A useful classroom walkthrough is:

```text
OpenAPI contract
      ↓
Swagger UI
      ↓
Swagger Codegen
      ↓
REST / synchronous RPI
      ↓
Inbound adapter
      ↓
Inbound port
      ↓
Application core
      ↓
Outbound port
      ↓
PostgreSQL adapter
      ↓
orders table
```

This single lab deliberately connects API contracts, synchronous communication, Hexagonal Architecture, persistence, and generated clients without hiding the architectural responsibilities behind framework code.
