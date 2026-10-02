# Cloud-Native Architecture Principles — Examples

This directory contains the runnable examples for the **Cloud-Native
Architecture Principles** block.

The examples are intentionally small. They focus on one architectural idea at a
time and are designed to be run locally during or after the lecture.

## Learning objectives

After completing this block, students should be able to:

- explain API First and Contract First using an OpenAPI contract and Swagger UI;
- explain how consumer needs shape API responses;
- distinguish an authoritative data store from a disposable cache;
- observe how timeouts and fallbacks isolate optional failures;
- explain how init and sidecar containers preserve a single concern;
- inspect liveness, readiness, logs, metrics, and request traces;
- inspect container lifecycle and runtime constraints;
- explain the seven cohesion levels and the eight coupling levels used in the lecture;
- connect simple code examples to selected SOLID principles.

## Examples and recommended sequence

| Step | Example | Main idea |
|---:|---|---|
| 1 | [`api-first/`](api-first/) | API First, Contract First, OpenAPI/Swagger UI, and consumer compatibility |
| 2 | [`consumer-first/`](consumer-first/) | Shape interfaces around consumer needs |
| 3 | [`polyglot-persistence/`](polyglot-persistence/) | Relational store and Redis cache |
| 4 | [`failure-isolation/`](failure-isolation/) | Timeout and graceful degradation |
| 5 | [`single-concern/`](single-concern/) | Main, init, and sidecar container responsibilities |
| 6 | [`high-observability/`](high-observability/) | Liveness, readiness, logs, metrics, and request tracing |
| 7 | [`container-constraints/`](container-constraints/) | Lifecycle signals and runtime limits |
| 8 | [`cohesion-coupling/`](cohesion-coupling/) | Seven cohesion levels and eight coupling levels |
| 9 | [`domain-solid/`](domain-solid/) | Domain boundaries and selected SOLID principles |

Each example includes its own `README.md` with the commands to run and the
behavior to observe.

## Requirements

- Docker Engine 24 or newer
- Docker Compose v2
- `curl`
- A Bash-compatible terminal for shell loops and environment variables
- Python 3.10+ only if you want to run `cohesion-coupling/` without Docker

Verify Docker:

```bash
docker --version
docker compose version
```

Windows users can run the commands from WSL or Git Bash.

## Running an example

Enter the selected directory and follow its README. Most examples use:

```bash
docker compose up -d --build
docker compose ps
docker compose logs
docker compose down -v
```

Run **one example at a time**, because several examples reuse port `8080`.

## Scope

These examples demonstrate architectural behavior, not production-ready
configurations. They do not require Kubernetes, a cloud account, or external
managed services.

## Clean up

Before moving to another Docker example, run:

```bash
docker compose down -v --remove-orphans
```
