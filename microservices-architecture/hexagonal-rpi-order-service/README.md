# Hexagonal Order Service — interchangeable REST adapters

This lab implements a small **Order Service** and uses one concrete example to connect several concepts from the Microservices Architecture module:

- synchronous **Remote Procedure Invocation (RPI)** over HTTP;
- **Hexagonal Architecture** with explicit inbound/outbound ports and adapters;
- **two alternative inbound REST adapters**: FastAPI and Flask;
- a single **`OrderUseCases` inbound port** shared by both adapters;
- a single **application core** that is independent of the web framework;
- **PostgreSQL** behind an `OrderRepository` outbound port;
- **OpenAPI**, Swagger UI, client generation, and optional server-skeleton generation;
- **Docker Compose** for running both adapters and Dockerized code-generation tools.

The main teaching point is simple:

> Replacing FastAPI with Flask changes the inbound adapter, not the application core.

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
- the application core does not depend on FastAPI, Flask, HTTP, SQLAlchemy, or PostgreSQL;
- the core depends on the `OrderRepository` outbound port;
- `PostgresOrderRepository` implements that port.

> **Important:** inbound adapters do not implement the inbound port. They translate transport-specific input into calls to the port. The application service implements the inbound port.

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
│   └── rpi_client.py
├── tests/
│   ├── test_order_service.py
│   └── test_rest_adapters.py
├── scripts/
│   ├── compare-rest-adapters.sh
│   ├── generate-swagger-client.sh
│   └── generate-openapi-client.sh
├── Makefile
└── docker-compose.yml
```

The `generated/` directory is intentionally not shown because it is created on demand and is excluded from Git. It can contain generated clients and the optional generated server skeleton used only for inspection.

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

It creates an `APIRouter`, validates HTTP input through Pydantic models, translates transport data to domain-oriented values, and calls only `OrderUseCases`.

### DTOs and Pydantic at the REST boundary

A **DTO (Data Transfer Object)** is a small object used to carry data across a boundary. In this lab, request/response DTOs represent the JSON shape exchanged through HTTP. They belong to the **REST adapter**, not to the domain model: `CreateOrderRequest` describes incoming transport data, while `OrderResponse` describes outgoing transport data.

**Pydantic** is a Python library for parsing, validating, and serializing structured data from type annotations. FastAPI integrates Pydantic directly, so `BaseModel` classes can be used as REST DTOs and FastAPI can automatically validate request bodies, serialize responses, and derive OpenAPI schemas.

```text
HTTP / JSON
    ↓
Pydantic DTOs              transport boundary
    ↓
OrderUseCases              application boundary
    ↓
Domain objects             application/domain
```

The important distinction is:

```text
CreateOrderRequest / OrderResponse  -> REST DTOs
Order                              -> domain entity
```

The DTOs may change when the HTTP contract changes; the domain entity should change only when the business model changes.

The adapter then calls the application port:

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

Framework-specific concepts stay in the adapter:

```text
APIRouter
Pydantic request/response models
HTTPException
HTTP status codes
```

None of these appear in the application core.

## 3. Flask as an alternative inbound adapter

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

Flask does **not** require Pydantic and does not automatically bind request bodies to typed models. In this lab the Flask adapter deliberately uses `request.get_json()`, plain Python dictionaries, explicit validation, and `jsonify()` so that the framework difference remains visible. Pydantic *could* also be added to a Flask application, but it would be an explicit adapter choice rather than a framework-integrated mechanism.

Conceptually, the Flask JSON dictionaries play the same transport role as the FastAPI DTOs: they carry data across the HTTP boundary and are translated before the application core is called.

### FastAPI vs Flask at the adapter boundary

| Concern | FastAPI adapter | Flask adapter |
|---|---|---|
| Route grouping | `APIRouter` | `Blueprint` |
| Route decorator | `@router.post(...)` | `@blueprint.post(...)` |
| Request parsing | Pydantic model binding | `request.get_json()` |
| Validation | Mostly automatic | Explicit/manual in this lab |
| Response conversion | response model | `jsonify()` |
| Core dependency | `OrderUseCases` | `OrderUseCases` |

The framework APIs differ. The application port does not.

## 4. Two composition roots, same core

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

## 5. Run both adapters

From this directory:

```bash
docker compose up --build
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

## 6. Call the same use case through FastAPI

```bash
curl -i -X POST http://localhost:8000/orders \
  -H 'Content-Type: application/json' \
  -d '{"restaurantId":42,"total":25.50}'
```

Execution path:

```text
HTTP / JSON
    ↓
FastAPI APIRouter
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

## 7. Call the same use case through Flask

```bash
curl -i -X POST http://localhost:5000/orders \
  -H 'Content-Type: application/json' \
  -d '{"restaurantId":42,"total":25.50}'
```

Execution path:

```text
HTTP / JSON
    ↓
Flask Blueprint
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

The outer framework changes; everything from `OrderUseCases` inward stays the same.

For a quick side-by-side demonstration:

```bash
./scripts/compare-rest-adapters.sh
```

## 8. One published REST contract

The explicit contract remains:

```text
openapi/order-api.yaml
```

It exposes:

```text
POST /orders
GET  /orders/{orderId}
```

Both adapters are intended to implement the same external contract. This is important: changing the framework should not silently change the API seen by consumers.

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

## 10. Test the core and adapters independently

Run:

```bash
docker compose run --rm order-fastapi pytest -q /app/tests
```

`test_order_service.py` tests the application core with an in-memory repository and no web framework.

`test_rest_adapters.py` injects a fake `OrderUseCases` implementation into both adapters. This proves that neither adapter requires the concrete `OrderApplicationService`.

Conceptually:

```text
FakeOrderUseCases
      ↑       ↑
      |       |
 FastAPI     Flask
 adapter    adapter
```

The same idea works on the outbound side with a fake repository.

## 11. Inspect PostgreSQL

```bash
docker compose exec postgres \
  psql -U orders -d orders -c '\\d orders'
```

```bash
docker compose exec postgres \
  psql -U orders -d orders -c 'SELECT * FROM orders ORDER BY id;'
```

The SQLAlchemy model is an outbound-adapter detail. The domain `Order` object does not depend on SQLAlchemy.

## 12. Optional: generate and inspect a REST server skeleton

The OpenAPI contract can generate not only clients but also a **server-side transport skeleton**. This is useful for showing what code generation can automate without confusing generated framework code with the application architecture.

The generator runs entirely in Docker through the optional `codegen` Compose profile:

```bash
make generate-server-skeleton
```

or equivalently:

```bash
docker compose --profile codegen run --rm openapi-server-generator
```

The generated project is written to:

```text
generated/openapi-fastapi-server/
```

The flow is:

```text
openapi/order-api.yaml
        |
        | OpenAPI Generator container
        v
generated FastAPI server skeleton
        |
        | inspect / compare
        v
handwritten FastAPI adapter
        |
        v
OrderUseCases
```

The generated skeleton contains HTTP/framework-facing code derived from the contract: routes, request/response models, and server plumbing. It does **not** know the Hexagonal Architecture chosen for this service and it does not invent `OrderUseCases`, `OrderApplicationService`, or `OrderRepository`.

That distinction is the teaching point:

```text
generated controller / route skeleton   -> transport/framework boundary
handwritten FastAPI adapter             -> inbound adapter
OrderUseCases                            -> application inbound port
OrderApplicationService                 -> application core
```

> **Important:** the generated server skeleton is an inspection artifact only. The running lab continues to use the handwritten FastAPI and Flask adapters. Generating or deleting `generated/` does not change the normal `docker compose up` runtime.

Because `generated/` is in `.gitignore`, generated framework code is reproducible from `order-api.yaml` and is not committed. To remove all generated artifacts:

```bash
make clean-generated
```

## 13. Generate a REST client

Swagger Codegen:

```bash
./scripts/generate-swagger-client.sh
```

OpenAPI Generator:

```bash
./scripts/generate-openapi-client.sh
```

The generated client depends on the published REST contract, not on whether the server implementation uses FastAPI or Flask.

The handwritten client can target either adapter. Running it directly with local Python is optional; it is not required for the Docker-based server-skeleton exercise.

```bash
python -m pip install requests
python client/rpi_client.py
```

FastAPI is the default. To call Flask instead:

```bash
ORDER_API_BASE_URL=http://localhost:5000 python client/rpi_client.py
```

## 14. Stop and clean up

```bash
docker compose down -v
```

## Teaching sequence

A useful classroom walkthrough is:

```text
1. Open OrderUseCases
        ↓
2. Show OrderApplicationService implements it
        ↓
3. Open FastAPI adapter
   APIRouter -> OrderUseCases
        ↓
4. Open Flask adapter
   Blueprint -> OrderUseCases
        ↓
5. Run the same POST through both adapters
        ↓
6. Show that the application core did not change
        ↓
7. Follow OrderRepository -> PostgreSQL adapter
        ↓
8. Run adapter tests with FakeOrderUseCases
        ↓
9. Return to OpenAPI: same external contract
        ↓
10. make generate-server-skeleton
        ↓
11. Inspect generated FastAPI transport code
        ↓
12. Compare it with the handwritten adapter and OrderUseCases
```

The key observation is not merely that FastAPI and Flask can expose the same endpoints. It is that **the application core has no reason to know which framework is currently connected to its inbound port**. Code generation can automate transport scaffolding, but it does not define the application's ports, domain model, or dependency direction.
