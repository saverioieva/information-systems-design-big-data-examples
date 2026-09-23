# Cloud-Native Architecture Labs

This directory contains the hands-on activities for the **Cloud-Native
Architecture** block of the *Cloud Introduction* module.

The labs use Docker and Docker Compose to turn the concepts presented in the
slides into small, observable experiments. They are not intended to reproduce a
complete cloud platform or a production environment.

## Learning objectives

After completing this block, students should be able to:

- distinguish images, containers, services, networks, and registries;
- explain why cloud-native applications favor disposable and stateless processes;
- connect Twelve-Factor principles to a containerized application;
- compare rolling, blue/green, and canary deployment strategies;
- distinguish a long-running microservice from a function-shaped handler;
- reason about the responsibility boundaries of IaaS, PaaS, and SaaS;
- collect application metrics with Prometheus and visualize them in Grafana.

## Labs and recommended sequence

| Step | Lab | Main idea |
|---:|---|---|
| 1 | [`architecture/`](architecture/) | Images, containers, services, networking, and reverse proxy |
| 2 | [`lifecycle/`](lifecycle/) | Build, start, inspect, stop, replace, and scale containers |
| 3 | [`twelve-factor/`](twelve-factor/) | Configuration, backing services, stateless processes, logs, and persistence |
| 4 | [`rolling/`](rolling/) | Replace service replicas gradually |
| 5 | [`blue-green/`](blue-green/) | Switch traffic between two complete environments |
| 6 | [`canary/`](canary/) | Expose a candidate version to a small traffic share |
| 7 | [`microservices-vs-serverless/`](microservices-vs-serverless/) | Compare a service API with a function-shaped handler |
| 8 | [`service-models/`](service-models/) | Explore simple responsibility-model analogies for IaaS, PaaS, and SaaS |
| 9 | [`monitoring/`](monitoring/) | Export metrics and inspect them with Prometheus and Grafana |

Each lab is self-contained and includes its own `README.md` with the commands to
run, observations to make, and questions to discuss.

## Requirements for this block

- Docker Engine 24 or newer
- Docker Compose v2
- A Bash-compatible terminal for commands that use `$(...)` or shell loops

Verify the installation:

```bash
docker --version
docker compose version
```

Windows users can run the commands from WSL or Git Bash.

## Running a lab

Enter the selected lab directory and follow its README. The commands used most
frequently are:

```bash
docker compose up -d --build   # build and start the lab
docker compose ps              # inspect its containers
docker compose logs -f         # follow application logs
docker compose down -v         # stop the lab and remove its data
```

Run **one lab at a time**, because multiple examples reuse the same host ports.

## Deployment strategies at a glance

| Strategy | Change mechanism | Initial blast radius | Main trade-off |
|---|---|---:|---|
| Rolling | Replace replicas gradually | Part of the service | Old and new versions coexist temporarily |
| Blue/Green | Switch traffic between environments | Complete candidate environment | Duplicate capacity is required |
| Canary | Increase candidate traffic gradually | Small user subset | Advanced routing and monitoring are required |

The deployment labs illustrate the core mechanisms. Production systems also
require readiness checks, security controls, automated rollback policies, and
more complete observability.

## Scope of the service-model examples

Docker Compose cannot reproduce the managed services of a real cloud provider.
The examples in `service-models/` are deliberately small analogies focused on
**who manages what**:

- **IaaS:** the user administers an operating-system environment;
- **PaaS:** the user changes application code while the platform supplies the runtime;
- **SaaS:** the user consumes a ready-made application without developing it.

The README inside each example explains where the analogy differs from a real
cloud service.

## Observability scope

The practical observability lab focuses on application metrics, Prometheus, and
Grafana. Centralized logging and the sidecar logging pattern remain theoretical
topics in the slides and are not implemented in this introductory block.

## Clean up

Before moving to another lab, run this command from the current lab directory:

```bash
docker compose down -v --remove-orphans
```
