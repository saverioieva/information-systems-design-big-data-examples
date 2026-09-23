# Cloud-Native Docker Examples

Hands-on examples for the **Information Systems Design and Big Data** course.
Each folder connects one concept from the Cloud Introduction module to a small,
self-contained Docker Compose lab.

## Prerequisites

- Docker Engine 24 or newer
- Docker Compose v2
- A Bash-compatible terminal for commands that use `$(...)` or shell loops

Verify the installation:

```bash
docker --version
docker compose version
```

Windows users can run the commands from WSL or Git Bash.

## Docker Compose essentials

```bash
docker compose up -d --build   # build and start
docker compose ps              # inspect containers
docker compose logs -f         # follow logs
docker compose down -v         # stop and remove lab data
```

Run one lab folder at a time because several examples use the same host ports.

## Recommended order

1. `architecture/` — images, containers, services, networking, and proxy
2. `lifecycle/` — build, run, stop, replace, and scale
3. `twelve-factor/` — apply cloud-native principles after the Docker introduction
4. `rolling/` — replace replicas gradually
5. `blue-green/` — switch between two complete environments
6. `canary/` — send a small traffic share to a new version
7. `microservices-vs-serverless/` — compare a service API with a function-shaped handler
8. `service-models/` — simple local analogies for IaaS, PaaS, and SaaS
9. `monitoring/` — application metrics with Prometheus and Grafana

Every directory contains its own `README.md` with commands and observations.

Centralized logging remains a theoretical topic in the slides. This introductory
package focuses its observability lab on metrics, Prometheus, and Grafana.

## Deployment strategy summary

| Strategy | Change mechanism | Initial blast radius | Main cost |
|---|---|---:|---|
| Rolling | Replace replicas gradually | Part of the service | Temporary version mixture |
| Blue/Green | Switch all traffic between environments | Entire new environment | Duplicate capacity |
| Canary | Increase traffic to the candidate gradually | Small user subset | Routing and monitoring complexity |

These labs demonstrate the mechanisms. Production systems also require health
checks, readiness checks, security controls, metrics, and automated rollback policies.

## Service-model limitation

Docker Compose cannot reproduce a real cloud provider. The IaaS, PaaS, and SaaS
labs are deliberately small **responsibility-model analogies**:

- IaaS: the user administers an operating-system environment.
- PaaS: the user changes application code while a platform definition supplies the runtime.
- SaaS: the user consumes a ready-made application without writing its code.

The individual READMEs state where each analogy differs from a real cloud service.

## Clean up

From an example directory:

```bash
docker compose down -v --remove-orphans
```
