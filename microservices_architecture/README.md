# Microservices Architecture — Examples

This directory contains the runnable examples for the **Microservices Architecture** block.

The examples are intentionally small and focus on architectural decisions rather than production concerns. The first lab shows how the **same FTGO requirements** can be decomposed using two different strategies:

- **decompose by business capability**;
- **decompose by subdomain / bounded context (DDD)**.

## Learning objectives

After completing this block, students should be able to:

- explain why service boundaries should be driven by the business domain rather than technical layers;
- distinguish a business capability from a DDD subdomain / bounded context;
- derive candidate microservices from the same set of functional requirements using both strategies;
- explain why the two strategies can produce different service boundaries;
- discuss when the two views reinforce each other and when a boundary needs refinement.

## Examples and recommended sequence

| Step | Example | Main idea |
|---:|---|---|
| 1 | [`decomposition/`](decomposition/) | Compare decomposition by business capability with decomposition by subdomain using the same FTGO supplier-management scenario |

## Requirements

- Docker Engine 24 or newer
- Docker Compose v2
- `curl`

Verify Docker:

```bash
docker --version
docker compose version
```

## Running the decomposition lab

Start from:

```bash
cd microservices_architecture/decomposition
```

Read [`scenario.md`](decomposition/scenario.md) first, then run the two implementations separately:

```bash
cd by_capability
# follow README.md
```

and:

```bash
cd ../by_subdomain
# follow README.md
```

Run one variant at a time because the examples intentionally reuse nearby local ports.

## Scope

These examples are teaching aids. They show **how to reason about service boundaries**; they are not complete FTGO implementations and are not production-ready configurations.
