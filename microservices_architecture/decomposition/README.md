# Decomposing FTGO into Microservices

## Goal

Use the **same functional requirements** to compare two service-decomposition strategies.

The scenario is documented in [`scenario.md`](scenario.md).

## The common requirements

We model a small part of FTGO supplier management:

- register a restaurant;
- update a restaurant menu;
- register a courier;
- update courier availability.

## A. Decompose by business capability

The high-level business capability is **Supplier Management**. In this version, one service owns both restaurant and courier supplier functions.

```text
Supplier Management
        ↓
 Supplier Service
   ├─ restaurants
   └─ couriers
```

Run [`by_capability/`](by_capability/) and observe that all four operations are exposed by a single deployable service.

## B. Decompose by subdomain / bounded context

The DDD view notices that restaurants and couriers use different concepts and rules. In this version, the domain is split into two bounded contexts.

```text
Restaurant subdomain  →  Restaurant Service
Courier subdomain     →  Courier Service
```

Run [`by_subdomain/`](by_subdomain/) and observe that the same four requirements are now implemented by two independently deployable services with separate models.

## Compare the decisions

| Question | By business capability | By subdomain / DDD |
|---|---|---|
| Starting point | What the business does | Domain concepts, language, and rules |
| Initial boundary | Supplier Management | Restaurant and Courier contexts |
| Result in this lab | One Supplier Service | Restaurant Service + Courier Service |
| Main strength | Stable business-oriented ownership | Explicit model boundaries and autonomy |
| Typical refinement signal | Different team/change/scale needs | Different ubiquitous language or invariants |

## Important conclusion

There is no rule saying that capability decomposition must always produce fewer services than DDD. This lab intentionally uses a case where the distinction is visible.

In a real system, both views are used together: **capabilities suggest candidate boundaries, while DDD helps validate and refine them**.
