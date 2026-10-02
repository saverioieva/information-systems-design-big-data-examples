# API-First, Contract-First, and Consumer Compatibility

## Goal

Observe three related ideas without introducing a complex microservice architecture:

- **API First**: the API is treated as a first-class interface between provider and consumer.
- **Contract First**: the public contract is defined in `openapi.yaml` independently from the Flask implementation.
- **Consumer compatibility**: compatible changes preserve what existing consumers depend on; breaking changes do not.

The example uses one small Flask service so the focus stays on the API contract.

## Structure

```text
api-first/
├── openapi.yaml        # Contract defined independently from the implementation
├── app.py              # Flask implementation + Swagger UI
├── consumer.py         # Existing consumer expectations
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## 1. Inspect the contract first

Before running or reading the implementation, open `openapi.yaml`.

The contract defines:

```text
GET /products/1
```

and requires the response fields:

```text
id
name
price_cents
```

The optional fields `currency` and `price_euros` illustrate a compatible additive evolution.

This is the key **Contract-First** idea: start from the interface consumers can rely on, not from the internal Flask code.

## 2. Start the baseline API

```bash
cd api-first
unset API_MODE
docker compose up -d --build
```

Check the API:

```bash
curl -s http://localhost:8080/products/1
```

Expected response:

```json
{"id":1,"name":"Notebook","price_cents":1200}
```

## 3. Explore the contract with Swagger UI

Open in a browser:

```text
http://localhost:8080/docs/
```

Swagger UI reads the same `openapi.yaml` contract used by the example. Use **Try it out** to call `GET /products/1`.

The raw OpenAPI document is also available at:

```text
http://localhost:8080/openapi.yaml
```

The important distinction is:

```text
openapi.yaml  -> defines the contract
Swagger UI    -> visualizes/tests the contract
app.py        -> implements the contract
consumer.py   -> represents an existing consumer
```

## 4. Run the existing consumer

```bash
docker compose exec api python consumer.py
```

Expected output:

```text
PASS: Notebook costs 1200 cents
```

The consumer relies on the fields `name` and `price_cents` defined by the contract.

## 5. Add fields without breaking the existing contract

```bash
export API_MODE=additive
docker compose up -d --force-recreate api
curl -s http://localhost:8080/products/1
docker compose exec api python consumer.py
```

The API now also returns `currency` and `price_euros`.

The existing consumer still works because the required field `price_cents` remains available.

Observe the same optional fields in Swagger UI:

```text
http://localhost:8080/docs/
```

## 6. Introduce a breaking change

```bash
export API_MODE=breaking
docker compose up -d --force-recreate api
curl -s http://localhost:8080/products/1
docker compose exec api python consumer.py
```

The implementation now returns `price` instead of the contracted `price_cents` field.

The consumer fails because the implementation no longer respects what the consumer expects from the contract.

Compare the runtime response with `openapi.yaml` / Swagger UI: the documented contract still requires `price_cents`.

## What to observe

- **API First** makes the API an explicit architectural boundary.
- **Contract First** defines that boundary before and independently from implementation details.
- **OpenAPI** provides the machine-readable contract.
- **Swagger UI** makes the OpenAPI contract visible and interactive.
- Adding optional information can preserve compatibility.
- Renaming or removing a required field is a breaking change for existing consumers.

## Clean up

```bash
unset API_MODE
docker compose down -v
```
