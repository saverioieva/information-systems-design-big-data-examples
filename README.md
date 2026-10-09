# Information Systems Design and Big Data — Examples

Hands-on examples for the **Information Systems Design and Big Data** course at
the Polytechnic University of Bari.

This repository complements the lecture slides with small, runnable examples.
The examples are organized by course block; each block focuses on a specific
set of architectural concepts and includes instructions for local experimentation.

## Available course blocks

| Directory | Topics |
|---|---|
| [`LocalStack/`](LocalStack/) | Local AWS emulation with LocalStack; introductory Docker Compose example for experimenting with cloud services without using a real AWS account |
| [`cloud-native-examples/`](cloud-native-examples/) | Docker fundamentals, Twelve-Factor principles, deployment strategies, service models, and monitoring |
| [`cloud-native-principles-examples/`](cloud-native-principles-examples/) | API-first, consumer-first design, persistence, failure isolation, single-concern containers, high observability, container constraints, cohesion/coupling levels, and SOLID principles |
| [`microservices-architecture/`](microservices-architecture/) | Microservice decomposition and service-boundary design; DDD; API evolution and versioning; synchronous REST RPI; Hexagonal Architecture; FastAPI/PostgreSQL adapters; OpenAPI/Swagger tooling; gRPC, Protocol Buffers, code generation, and RPC interaction models |

Additional examples may be added as the course progresses.

## Getting started

Clone the repository:

```bash
git clone https://github.com/saverioieva/information-systems-design-big-data-examples.git
cd information-systems-design-big-data-examples
```

Then open the course block you want to study:

- [`LocalStack/LocalStackIntro/`](LocalStack/LocalStackIntro/)
- [`cloud-native-examples/README.md`](cloud-native-examples/README.md)
- [`cloud-native-principles-examples/README.md`](cloud-native-principles-examples/README.md)
- [`microservices-architecture/README.md`](microservices-architecture/README.md)

The block-level README files contain the recommended sequence, requirements,
and commands for running their examples.

## How to use the examples

1. Follow the order suggested for the selected course block.
2. Run one example at a time.
3. Read the observations and comparison notes before moving to the next example.
4. Stop and clean up the current example before starting another one.

Most examples use Docker Compose. Typical commands are:

```bash
docker compose up -d --build
docker compose ps
docker compose logs
docker compose down -v
```

## Scope

These examples are designed for teaching and local experimentation. They
illustrate architectural concepts but do not represent complete production
configurations.
