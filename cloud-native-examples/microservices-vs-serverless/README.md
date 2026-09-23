# Microservice API and Function-Shaped Handler

## Goal

Compare two programming interfaces:

- `microservice`: a long-running HTTP API with multiple endpoints
- `function`: a small handler that processes one event-shaped request

Both examples run as always-on containers under Docker Compose. The function
container is therefore **serverless-like**, not a real serverless runtime. A
cloud serverless platform would also manage startup, scaling, and shutdown.

## Start

```bash
cd microservices-vs-serverless
docker compose up -d --build
docker compose ps
```

## Test the microservice

```bash
curl http://localhost:8080/microservice/hello

curl -X POST http://localhost:8080/microservice/sum \
  -H "Content-Type: application/json" \
  -d '{"a":4,"b":7}'
```

The service exposes separate operations and remains available for many requests.

## Test the function-shaped handler

```bash
curl -X POST http://localhost:8080/function/ --data "Ada"
```

The handler accepts one input event and returns one result. Observe that the
container still remains running:

```bash
docker compose ps
docker compose logs function
```

## Discussion

| Property | Microservice in this lab | Function-shaped handler in this lab |
|---|---|---|
| Interface | Multiple HTTP routes | One event handler |
| Process | Always running | Always running under Compose |
| Automatic scale-to-zero | No | No |
| True cloud serverless behavior | No | Requires a serverless platform |

## Clean up

```bash
docker compose down -v
```
