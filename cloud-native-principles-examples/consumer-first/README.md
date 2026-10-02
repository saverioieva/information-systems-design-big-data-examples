# Consumer-First Principle

## Goal

Observe the difference between an API shaped by its **internal data model** and
an API shaped by the **needs of its consumers**.

This example deliberately uses **one small FastAPI application in one
container**. It is not intended to introduce API Gateway, BFF, or other
microservice-specific patterns. The focus is only on the Consumer-First idea.

## Scenario

The application stores a customer record containing both useful business data
and internal implementation details:

```text
Customer record
├── first_name
├── last_name
├── email
├── birth_date
├── policy_id
├── policy_status
├── next_payment_eur
├── internal_risk_score   <- internal detail
└── database_version      <- internal detail
```

Two consumers need different information:

```text
Mobile application                 Support application
- customer name                    - customer id
- policy status                    - customer name
- next payment                     - email
                                   - policy id
                                   - policy status
```

## 1. Start the example

```bash
cd consumer-first
docker compose up -d --build
```

Check that the API is running:

```bash
curl -s http://localhost:8080/docs > /dev/null && echo "API is running"
```

## 2. Observe an implementation-first response

```bash
curl -s http://localhost:8080/implementation-first/customers/42
```

The endpoint returns the complete internal record, including fields such as:

```text
internal_risk_score
database_version
```

The API contract is therefore driven by the implementation rather than by a
specific consumer need.

## 3. Observe the mobile consumer

The mobile application only needs the customer name, policy status, and next
payment:

```bash
curl -s http://localhost:8080/consumer-first/mobile/customers/42
```

Expected shape:

```json
{
  "name": "Alice Brown",
  "policy_status": "ACTIVE",
  "next_payment_eur": 120.0
}
```

Run the small consumer check:

```bash
docker compose exec api python consumer.py mobile
```

Expected result:

```text
PASS: the response contains exactly the data this consumer needs
```

## 4. Observe a different consumer

A support operator needs a different view of the same customer:

```bash
curl -s http://localhost:8080/consumer-first/support/customers/42
```

Run the support consumer check:

```bash
docker compose exec api python consumer.py support
```

The response contains the information needed by support without exposing the
internal risk score or database version.

## What to observe

- Start from **who consumes the service and what that consumer needs**.
- Do not expose the internal data model automatically as the API contract.
- Different consumers may need different subsets or representations of the
  same underlying data.
- Consumer First determines **what the interface should provide**; API First
  defines and manages that interface as a first-class contract.

## Clean up

```bash
docker compose down -v --remove-orphans
```
