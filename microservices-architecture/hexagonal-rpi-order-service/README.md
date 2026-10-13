# Hexagonal Order Service — interchangeable REST adapters

This lab implements a small **Order Service** and connects several concepts from the Microservices Architecture module:

- synchronous **Remote Procedure Invocation (RPI)** over HTTP;
- **Hexagonal Architecture** with explicit inbound/outbound ports and adapters;
- **two alternative inbound REST adapters**: FastAPI and Flask;
- one framework-independent **`OrderUseCases` inbound port** shared by both adapters;
- one **application core** that is independent of the web framework;
- **PostgreSQL** behind an `OrderRepository` outbound port;
- **OpenAPI**, Swagger UI, Swagger Codegen, and OpenAPI Generator;
- **Docker Compose** for the services, code-generation tools, tests, and clients.

The main teaching point is:

> Replacing FastAPI with Flask changes the inbound adapter, not the application core.

A second practical goal is reproducibility: **no local Python environment is required**. Docker Compose runs the application, code generators, handwritten client, and generated clients.

## Architecture

```text
                         Order Service

 HTTP / JSON                                  HTTP / JSON
     |                                             |
     v                                             v
+--------------------+                    +--------------------+
| FastAPI Adapter    |                    | Flask Adapter      |
| APIRouter          |                    | Blueprint          |
+---------+----------+                    +---------+----------+
          \                                         /
           \                                       /
            +------------ depends on -------------+
                              |
                              v
                    (OrderUseCases)
                      inbound port
                              ^
                              | implements
                              |
                 +------------+-------------+
                 | OrderApplicationService  |
                 |     application core     |
                 +------------+-------------+
                              |
                              | depends on
                              v
                    (OrderRepository)
                      outbound port
                              ^
                              | implements
                              |
                 +------------+-------------+
                 | PostgresOrderRepository  |
                 |     outbound adapter     |
                 +------------+-------------+
                              |
                              v
                          PostgreSQL
```

The dependency direction is always toward abstractions and the core:

- the **FastAPI adapter** depends on `OrderUseCases`;
- the **Flask adapter** also depends on `OrderUseCases`;
- `OrderApplicationService` implements `OrderUseCases`;
- the application core does not depend on FastAPI, Flask, Pydantic, HTTP, SQLAlchemy, or PostgreSQL;
- the core depends on the `OrderRepository` outbound port;
- `PostgresOrderRepository` implements that port.

> **Important:** inbound adapters do not implement the inbound port. They translate transport-specific input into calls to the port. The application service implements the inbound port.

## Requirements

Only these tools are required on the host:

- Docker Engine;
- Docker Compose v2.

`curl` is useful for manual HTTP calls but is not required to run the Python clients.

Verify Docker:

```bash
docker --version
docker compose version
```

## Project structure

```text
hexagonal-rpi-order-service/
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
│       │   ├── inbound/
│       │   │   ├── fastapi/
│       │   │   │   └── routes.py
│       │   │   └── flask/
│       │   │       └── routes.py
│       │   └── outbound/postgres/
│       │       ├── models.py
│       │       └── repository.py
│       ├── infrastructure/
│       │   └── database.py
│       ├── main_fastapi.py
│       ├── main_flask.py
│       └── main.py
├── client/
│   ├── Dockerfile
│   ├── Dockerfile.swagger-generated
│   ├── Dockerfile.openapi-generated
│   ├── requirements.txt
│   ├── rpi_client.py
│   ├── swagger_generated_client.py
│   └── openapi_generated_client.py
├── tests/
│   ├── test_order_service.py
│   └── test_rest_adapters.py
├── scripts/
│   ├── compare-rest-adapters.sh
│   ├── generate-swagger-client.sh
│   ├── generate-openapi-client.sh
│   ├── run-rpi-client.sh
│   ├── run-swagger-generated-client.sh
│   └── run-openapi-generated-client.sh
├── generated/                 # created by the generators; ignored by Git
└── docker-compose.yml
```

## 1. Start from the inbound port

The application exposes its use cases through one framework-independent abstraction:

```python
class OrderUseCases(ABC):
    @abstractmethod
    def create_order(self, restaurant_id: int, total: Decimal) -> Order:
        ...

    @abstractmethod
    def get_order(self, order_id: int) -> Order | None:
        ...
```

The application core implements that port:

```python
class OrderApplicationService(OrderUseCases):
    def __init__(self, repository: OrderRepository) -> None:
        self._repository = repository
```

This is the stable boundary both REST adapters call.

## 2. FastAPI as an inbound adapter

The FastAPI adapter is in:

```text
app/src/order_service/adapters/inbound/fastapi/routes.py
```

It creates an `APIRouter`, receives HTTP/JSON data, validates it through Pydantic models, and invokes only `OrderUseCases`:

```python
def build_order_router(use_cases: OrderUseCases) -> APIRouter:
    router = APIRouter(prefix="/orders", tags=["orders"])

    @router.post("")
    def create_order(request: CreateOrderRequest) -> OrderResponse:
        order = use_cases.create_order(
            request.restaurantId,
            Decimal(str(request.total)),
        )
        return OrderResponse.from_domain(order)

    return router
```

Framework-specific concepts remain outside the core:

```text
APIRouter
Pydantic request/response models
HTTPException
HTTP status codes
```

## 3. Pydantic DTOs are not domain models

Pydantic is used because it integrates naturally with FastAPI for HTTP-boundary concerns:

```text
JSON request
    ↓
Pydantic DTO
    ↓ validation / conversion
FastAPI adapter
    ↓
OrderUseCases
    ↓
Application core / domain
```

For example, `CreateOrderRequest` and `OrderResponse` describe the **REST representation** of an order. They are transport DTOs owned by the FastAPI adapter.

The domain entity is separate:

```text
CreateOrderRequest / OrderResponse   -> REST adapter DTOs
Order                               -> domain model
```

This distinction is intentional:

- Pydantic validates and serializes REST data;
- FastAPI uses the models to generate its OpenAPI description;
- the application core does **not** import Pydantic;
- changing or removing FastAPI must not require changing the domain model.

Pydantic is therefore a **framework/boundary detail**, not a requirement of Hexagonal Architecture.

## 4. Flask as an alternative inbound adapter

The Flask adapter is in:

```text
app/src/order_service/adapters/inbound/flask/routes.py
```

It exposes the same REST contract through a Flask `Blueprint`:

```python
def build_order_blueprint(use_cases: OrderUseCases) -> Blueprint:
    blueprint = Blueprint("orders", __name__, url_prefix="/orders")

    @blueprint.post("")
    def create_order():
        payload = request.get_json()
        order = use_cases.create_order(
            payload["restaurantId"],
            Decimal(str(payload["total"])),
        )
        return jsonify(...), 201

    return blueprint
```

Again, the adapter depends on `OrderUseCases`, not on `OrderApplicationService`.

### FastAPI vs Flask at the adapter boundary

| Concern | FastAPI adapter | Flask adapter |
|---|---|---|
| Route grouping | `APIRouter` | `Blueprint` |
| Route decorator | `@router.post(...)` | `@blueprint.post(...)` |
| Request parsing | Pydantic model binding | `request.get_json()` |
| Validation | Mostly automatic | Explicit/manual in this lab |
| Response conversion | Pydantic response model | `jsonify()` |
| Core dependency | `OrderUseCases` | `OrderUseCases` |

The framework APIs differ. The application port does not.

## 5. Two composition roots, same core

FastAPI wiring:

```python
repository = PostgresOrderRepository(SessionFactory)
order_service = OrderApplicationService(repository)

app = FastAPI(...)
app.include_router(build_order_router(order_service))
```

Flask wiring:

```python
repository = PostgresOrderRepository(SessionFactory)
order_service = OrderApplicationService(repository)

app = Flask(__name__)
app.register_blueprint(build_order_blueprint(order_service))
```

The composition roots are:

```text
main_fastapi.py
main_flask.py
```

`main.py` remains a small compatibility alias to the FastAPI entry point.

## 6. Start the complete stack

From this directory:

```bash
docker compose up --build -d
```

Services:

| Component | URL |
|---|---|
| FastAPI REST adapter | http://localhost:8000 |
| FastAPI Swagger UI | http://localhost:8000/docs |
| Flask REST adapter | http://localhost:5000 |
| Swagger UI for explicit `order-api.yaml` | http://localhost:8080 |
| PostgreSQL | `localhost:5432` |

Both REST adapters use the same application-core code and the same PostgreSQL schema.

## 7. Call the same use case through FastAPI and Flask

FastAPI:

```bash
curl -i -X POST http://localhost:8000/orders \
  -H 'Content-Type: application/json' \
  -d '{"restaurantId":42,"total":25.50}'
```

Flask:

```bash
curl -i -X POST http://localhost:5000/orders \
  -H 'Content-Type: application/json' \
  -d '{"restaurantId":42,"total":25.50}'
```

Both requests eventually execute the same path from the port inward:

```text
REST adapter
     ↓
OrderUseCases
     ↓
OrderApplicationService
     ↓
OrderRepository
     ↓
PostgresOrderRepository
     ↓
PostgreSQL
```

For a quick side-by-side demonstration:

```bash
./scripts/compare-rest-adapters.sh
```

## 8. One published REST contract

The explicit contract is:

```text
openapi/order-api.yaml
```

It exposes:

```text
POST /orders
GET  /orders/{orderId}
```

Both adapters are intended to implement the same external contract. Changing the framework should not silently change the API seen by consumers.

FastAPI also generates an OpenAPI description automatically at:

```text
http://localhost:8000/docs
```

The standalone Swagger UI reads the repository contract at:

```text
http://localhost:8080
```

This gives a useful classroom comparison between an **explicit published contract** and a **framework-generated description**.

## 9. Outbound port and PostgreSQL adapter

The core depends on the abstraction:

```python
class OrderRepository(ABC):
    @abstractmethod
    def save(self, order: Order) -> Order:
        ...

    @abstractmethod
    def get_by_id(self, order_id: int) -> Order | None:
        ...
```

PostgreSQL implements it:

```python
class PostgresOrderRepository(OrderRepository):
    ...
```

Therefore the complete dependency structure is symmetrical:

```text
FastAPI / Flask  ->  OrderUseCases  <-  OrderApplicationService
                                         |
                                         v
                                  OrderRepository
                                         ^
                                         |
                              PostgresOrderRepository
```

## 10. Test the core and adapters in Docker

Run:

```bash
docker compose run --rm order-fastapi pytest -q /app/tests
```

`test_order_service.py` tests the application core with an in-memory repository and no web framework.

`test_rest_adapters.py` injects a fake `OrderUseCases` implementation into both adapters. This proves that neither adapter requires the concrete `OrderApplicationService`.

```text
FakeOrderUseCases
      ↑       ↑
      |       |
 FastAPI     Flask
 adapter    adapter
```

## 11. Inspect PostgreSQL

```bash
docker compose exec postgres \
  psql -U orders -d orders -c '\d orders'
```

```bash
docker compose exec postgres \
  psql -U orders -d orders -c 'SELECT * FROM orders ORDER BY id;'
```

The SQLAlchemy model is an outbound-adapter detail. The domain `Order` object does not depend on SQLAlchemy.

## 12. Generate clients entirely with Docker

No local Swagger Codegen, Java, Python, or `pip` installation is required.

### Swagger Codegen

The Compose service uses `swaggerapi/swagger-codegen-cli-v3:3.0.81`:

```bash
./scripts/generate-swagger-client.sh
```

Equivalent command:

```bash
docker compose run --rm swagger-codegen
```

Generated code is written to:

```text
generated/swagger-python-client/
```

### OpenAPI Generator

```bash
./scripts/generate-openapi-client.sh
```

Equivalent command:

```bash
docker compose run --rm openapi-generator
```

Generated code is written to:

```text
generated/openapi-python-client/
```

The generated clients depend on the **published OpenAPI contract**, not on whether the server implementation uses FastAPI or Flask.

## 13. Run clients entirely with Docker

### Handwritten RPI client

Run the handwritten client against FastAPI:

```bash
./scripts/run-rpi-client.sh
```

Equivalent command:

```bash
docker compose run --rm rpi-client
```

The client container calls the service by its Compose DNS name:

```text
rpi-client -> http://order-fastapi:8000
```

To target Flask instead:

```bash
docker compose run --rm \
  -e ORDER_API_BASE_URL=http://order-flask:5000 \
  rpi-client
```

### Swagger-generated client

Generate, build, and run it with one script:

```bash
./scripts/run-swagger-generated-client.sh
```

The script performs:

```text
order-api.yaml
      ↓
Swagger Codegen container
      ↓
generated/swagger-python-client
      ↓
Docker image for the generated client
      ↓
Order Service
```

To run the already generated/built client again:

```bash
docker compose run --rm swagger-generated-client
```

### OpenAPI Generator client

Generate, build, and run it with:

```bash
./scripts/run-openapi-generated-client.sh
```

No Python package is installed on the host in any of these flows.

## 14. Why the client is also containerized

The Docker-first setup makes the teaching environment reproducible:

```text
Host machine
    |
    | only Docker / Compose
    v
+--------------------------------------+
| Swagger/OpenAPI generator containers |
| Python client containers             |
| FastAPI / Flask containers           |
| PostgreSQL container                 |
+--------------------------------------+
```

This avoids mixing two setup models such as "server in Docker, client in a local virtual environment".

## 15. Stop and clean up

```bash
docker compose down -v
```

Generated source code remains under `generated/` so it can be inspected. The directory is ignored by Git.

## Teaching sequence

A useful classroom walkthrough is:

```text
1. Open OrderUseCases
        ↓
2. Show OrderApplicationService implements it
        ↓
3. Open FastAPI adapter
   APIRouter + Pydantic DTOs -> OrderUseCases
        ↓
4. Open Flask adapter
   Blueprint + JSON parsing -> OrderUseCases
        ↓
5. Run the same POST through both adapters
        ↓
6. Show that the application core did not change
        ↓
7. Follow OrderRepository -> PostgreSQL adapter
        ↓
8. Run adapter tests with FakeOrderUseCases
        ↓
9. Inspect the explicit OpenAPI contract
        ↓
10. Generate a client in a Docker tool container
        ↓
11. Run that generated client in another Docker container
```

The key observation is not merely that FastAPI and Flask can expose the same endpoints. It is that **the application core has no reason to know which framework is connected to its inbound port**, and client tooling can remain reproducible without installing language-specific tools on the host.
