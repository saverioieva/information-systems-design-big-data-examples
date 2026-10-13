# Scenario — FTGO Supplier Management

FTGO works with two kinds of suppliers:

- **restaurants**, which publish menus and accept food orders;
- **couriers**, which advertise availability and perform deliveries.

For the lab we keep only four requirements:

1. Register a restaurant.
2. Update a restaurant menu.
3. Register a courier.
4. Update courier availability.

The requirements are deliberately small so that the interesting part is the **boundary decision**, not the amount of code.

## View 1 — Business capability

Ask:

> **What does the business do?**

At a high level, the four requirements belong to the capability **Supplier Management**. A valid first decomposition is therefore one `Supplier Service` that owns both restaurant and courier management.

This is not a statement that the service must remain this size forever. A capability can later be decomposed into sub-capabilities if different ownership, scaling, change frequency, or operational needs justify a split.

```text
Supplier Management
├── Restaurant management
└── Courier management

           ↓

      Supplier Service
```

## View 2 — Subdomain / bounded context

Ask:

> **Where do meaning, rules, and models differ?**

Restaurants and couriers use different language and obey different rules:

| Restaurant context | Courier context |
|---|---|
| menu | availability |
| menu items | current location |
| accepting orders | delivery assignment |
| restaurant identity | courier identity |

DDD therefore suggests two bounded contexts with independent models:

```text
Restaurant subdomain  →  Restaurant Service
Courier subdomain     →  Courier Service
```

## What the comparison should teach

The two approaches start from different questions:

- **Business capability:** *What does the organization do?*
- **Subdomain / DDD:** *Where do business concepts, vocabulary, and rules form distinct models?*

They are complementary, not mutually exclusive. A capability map is often a good way to discover candidate services; DDD can then refine boundaries when one capability contains clearly different domain models.
