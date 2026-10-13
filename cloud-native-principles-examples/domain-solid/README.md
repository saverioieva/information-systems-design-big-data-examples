# Domain Boundaries and SOLID

## Goal

Keep the **quote calculation** independent from the way product prices are retrieved.

The same domain rule can work with different catalog implementations:

- an in-memory catalog;
- an HTTP catalog;
- a discount catalog.

The important idea is that the **domain logic does not know where the price comes from**.  
It only depends on a small catalog abstraction exposing the operation it needs:

```text
price_cents(...)
```

This example therefore demonstrates both **SOLID principles** and a first, simplified
view of **Hexagonal Architecture (Ports and Adapters)**.

---

## Architecture overview

Conceptually, the example is organized as follows:

```text
                    HTTP request
                        |
                        v
              +-------------------+
              |   HTTP handling   |
              |  /quote endpoint  |
              +---------+---------+
                        |
                        v
              +-------------------+
              |   Domain logic    |
              |      quote()      |
              +---------+---------+
                        |
                        v
              +-------------------+
              |   Catalog Port    |
              |  price_cents(...) |
              +---------+---------+
                        |
          +-------------+-------------+
          |             |             |
          v             v             v
 +---------------+ +-------------+ +----------------+
 | MemoryCatalog | | HttpCatalog | | DiscountCatalog|
 +---------------+ +-------------+ +----------------+
```

The **domain** is in the center. It knows only the catalog operation it requires.

The concrete implementations are outside the domain and can be selected at runtime.

This is the main idea behind **Hexagonal Architecture**:

```text
Domain / Application Core
        |
        v
      Ports
        |
        v
     Adapters
```

In this example:

- the `/quote` HTTP endpoint acts as a simplified **driving/inbound adapter**;
- the catalog abstraction acts as an **outbound port**;
- `MemoryCatalog`, `HttpCatalog`, and `DiscountCatalog` are **outbound adapters**.

Hexagonal Architecture will be discussed in more detail later. Here, the important
point is the **direction of dependencies**: the domain depends on an abstraction,
not on a specific database, HTTP service, or other infrastructure technology.

---

## 1. Start with the in-memory catalog

```bash
cd domain-solid
unset CATALOG_BACKEND
docker compose up -d --build
curl -s 'http://localhost:8080/quote?quantity=2'
```

Expected total:

```text
2400 cents
```

With the default configuration, the order service uses `MemoryCatalog`.

Conceptually:

```text
GET /quote?quantity=2
        |
        v
     quote()
        |
        v
  price_cents(...)
        |
        v
  MemoryCatalog
```

The quote calculation does not access a database or another service directly.
It asks the catalog abstraction for the price and performs the domain calculation.

### What this demonstrates

**SRP - Single Responsibility Principle**

Different parts of the application have different responsibilities:

```text
HTTP layer       -> handles HTTP requests and responses
quote()          -> performs the quote calculation
catalog adapter  -> retrieves the product price
```

The quote calculation is therefore not responsible for HTTP communication or
price storage.

**ISP - Interface Segregation Principle**

The domain does not need a large catalog interface.

It only requires the operation needed by the use case:

```text
price_cents(...)
```

The domain is therefore not forced to depend on unrelated catalog operations.

**DIP - Dependency Inversion Principle**

The domain logic does not depend directly on `MemoryCatalog`.

Instead:

```text
quote()
   |
   v
catalog abstraction
   |
   v
MemoryCatalog
```

The concrete implementation is selected outside the domain logic.

### Verify the boundary

Stop the HTTP catalog service:

```bash
docker compose stop catalog
curl -s 'http://localhost:8080/quote?quantity=2'
```

The request still works.

Why?

Because the selected implementation is `MemoryCatalog`, so the domain does not
depend on the external HTTP catalog.

This is an important boundary:

```text
External catalog DOWN
        |
        X

MemoryCatalog still available
        |
        v
quote() still works
```

---

## 2. Replace the catalog with an HTTP adapter

Start the catalog service and select the HTTP implementation:

```bash
docker compose start catalog
export CATALOG_BACKEND=http
docker compose up -d --force-recreate orders
curl -s 'http://localhost:8080/quote?quantity=2'
```

The quote calculation is unchanged.

Only the implementation used to retrieve the price changes:

```text
Before

quote()
   |
   v
MemoryCatalog
```

```text
Now

quote()
   |
   v
HttpCatalog
   |
   v
catalog service
```

The domain still calls the same catalog operation.

### What this demonstrates

**LSP - Liskov Substitution Principle**

`MemoryCatalog` and `HttpCatalog` can replace each other because they provide the
behavior required by the same catalog contract.

From the point of view of the domain:

```text
Catalog Port
    ^
    |
 +--+----------+
 |             |
MemoryCatalog  HttpCatalog
```

The domain does not need to change when one valid implementation is replaced by
another.

**DIP - Dependency Inversion Principle**

The high-level domain rule still depends on the catalog abstraction, while the
infrastructure-specific HTTP implementation depends on that contract.

The dependency direction is therefore:

```text
Domain ---> Catalog abstraction <--- HttpCatalog
```

rather than:

```text
Domain ---> HttpCatalog
```

### Observe an infrastructure failure

Stop the catalog service:

```bash
docker compose stop catalog
curl -i 'http://localhost:8080/quote?quantity=2'
```

The request returns `503`.

This does **not** mean that the domain calculation changed.

It means that the currently selected adapter depends on an external network service
that is unavailable.

Conceptually:

```text
quote()
   |
   v
Catalog Port
   |
   v
HttpCatalog
   |
   X
catalog service unavailable
```

The domain boundary remains the same, while the failure belongs to the selected
infrastructure adapter.

---

## 3. Add a different catalog implementation

Select the discount catalog:

```bash
export CATALOG_BACKEND=discount
docker compose up -d --force-recreate orders
curl -s 'http://localhost:8080/quote?quantity=2'
```

Expected total:

```text
2000 cents
```

The important observation is that `quote()` is unchanged.

Only the catalog implementation has changed:

```text
quote()
   |
   v
Catalog Port
   |
   v
DiscountCatalog
```

### What this demonstrates

**OCP - Open/Closed Principle**

The quote calculation is:

```text
open for extension
```

because new catalog implementations can be introduced,

but:

```text
closed for modification
```

because the existing `quote()` function does not need to be rewritten.

For example:

```text
Catalog Port
    ^
    |
    +-- MemoryCatalog
    |
    +-- HttpCatalog
    |
    +-- DiscountCatalog
    |
    +-- FutureCatalog
```

A new adapter can extend the system without changing the core domain rule.

**LSP - Liskov Substitution Principle**

`DiscountCatalog` can also be used wherever the catalog contract is expected,
provided that it preserves the expected contract of `price_cents(...)`.

---

## 4. SOLID principles in this example

### SRP - Single Responsibility Principle

Each part has a focused responsibility.

```text
quote()          -> quote calculation
HTTP layer       -> request/response handling
MemoryCatalog    -> in-memory price retrieval
HttpCatalog      -> remote price retrieval
DiscountCatalog  -> discounted price retrieval
```

A change in HTTP communication should not require changing the quote rule, and a
change in the quote rule should not require rewriting the catalog adapters.

### OCP - Open/Closed Principle

New catalog strategies can be added without modifying `quote()`.

```text
existing domain logic
        |
        v
   Catalog Port
        ^
        |
 new implementation
```

The system is extended by adding another implementation rather than by adding
infrastructure-specific branches inside the domain calculation.

### LSP - Liskov Substitution Principle

All valid catalog implementations can be substituted through the same contract.

```text
MemoryCatalog
HttpCatalog
DiscountCatalog
     |
     v
same expected catalog behavior
```

The caller should not need to know which concrete implementation is being used.

### ISP - Interface Segregation Principle

The domain depends only on the operation it needs:

```text
price_cents(...)
```

It does not depend on a large interface containing unrelated catalog operations.

A small port makes the dependency easier to understand, test, and replace.

### DIP - Dependency Inversion Principle

The domain does not depend on concrete infrastructure.

```text
Bad dependency

quote() ---> HttpCatalog
```

Instead:

```text
Preferred dependency

             +--> MemoryCatalog
             |
quote() ---> Catalog Port ---> HttpCatalog
             |
             +--> DiscountCatalog
```

The high-level domain rule depends on an abstraction, and concrete adapters provide
the implementation.

---

## 5. Connection with Hexagonal Architecture

This example is intentionally small, but its structure anticipates
**Hexagonal Architecture**, also known as **Ports and Adapters**.

The core idea is to protect the domain from infrastructure details.

```text
                 Outside the application
                         |
                         v
                +----------------+
                | HTTP endpoint  |
                | inbound adapter|
                +-------+--------+
                        |
                        v
             +----------------------+
             |   Application/Domain |
             |       quote()        |
             +----------+-----------+
                        |
                  outbound port
                        |
                        v
             +----------------------+
             |   price_cents(...)   |
             +----------+-----------+
                        |
          +-------------+-------------+
          |             |             |
          v             v             v
       Memory         HTTP         Discount
       Adapter        Adapter       Adapter
```

The key rule is:

> **Infrastructure depends on the domain boundary; the domain should not depend on
> infrastructure details.**

This gives the application several useful properties:

- the domain can be tested without network services;
- infrastructure implementations can be replaced;
- new adapters can be added without rewriting the business rule;
- technical concerns remain outside the core domain logic.

This example introduces the idea only at a high level. A later example can make
the full Hexagonal Architecture structure explicit with dedicated **ports**,
**inbound adapters**, **outbound adapters**, and an **application core**.

---

## What to observe

After running all three configurations, compare what changes and what remains
stable:

```text
                     Memory       HTTP       Discount
                     Catalog      Catalog    Catalog
                        \           |          /
                         \          |         /
                          +---------+--------+
                                    |
                                    v
                              Catalog Port
                                    |
                                    v
                                 quote()
```

What changes:

- the catalog implementation;
- the infrastructure used to retrieve the price;
- the resulting price when a different pricing strategy is selected.

What does **not** change:

- the `quote()` domain function;
- the catalog contract used by the domain;
- the responsibility of the HTTP layer.

This separation is the main lesson of the example.

---

## Clean up

```bash
unset CATALOG_BACKEND
docker compose down -v
```
