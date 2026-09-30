# High Observability Principle

## Goal

Show how a container exposes enough external signals to understand its runtime
state without inspecting its internal implementation.

This example focuses on four observable signals:

- **liveness and process health** through `/livez`;
- **readiness** through `/readyz`;
- **metrics** through `/metrics`, Prometheus, and Grafana;
- **logs and request traces** correlated with request and trace IDs.

## 1. Start the example

```bash
cd high-observability
docker compose up -d --build
docker compose ps
```

Open:

- Application: http://localhost:8080/catalog
- Raw metrics: http://localhost:8080/metrics
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000
- Jaeger: http://localhost:16686

Grafana credentials:

```text
username: admin
password: admin
```

## 2. Check liveness and readiness

Check that the process is alive:

```bash
curl -s http://localhost:8080/livez
```

Check that the application is ready to receive traffic:

```bash
curl -i http://localhost:8080/readyz
```

The two endpoints answer different questions: the process can be alive while the
application is temporarily not ready to serve traffic.

## 3. Simulate alive but not ready

Change only the readiness state:

```bash
curl -s -X POST http://localhost:8080/admin/readiness/not-ready
```

Check both signals again:

```bash
curl -i http://localhost:8080/livez
curl -i http://localhost:8080/readyz
```

`/livez` still returns `200`, while `/readyz` returns `503`.

Restore readiness:

```bash
curl -s -X POST http://localhost:8080/admin/readiness/ready
```

## 4. Generate requests and inspect logs

Send a request with a known correlation ID:

```bash
curl -i \
  -H 'X-Request-ID: lecture-demo' \
  http://localhost:8080/catalog
```

Inspect the application logs:

```bash
docker compose logs app | grep lecture-demo
```

The structured log contains the request ID, trace ID, status, and request
duration.

Generate more traffic:

```bash
for i in $(seq 1 20); do curl -s http://localhost:8080/catalog > /dev/null; done
```

Generate one failed request:

```bash
curl -i 'http://localhost:8080/catalog?fail=1'
```

## 5. Inspect metrics

View the raw Prometheus metrics:

```bash
curl -s http://localhost:8080/metrics | grep observability_
```

In Prometheus, try:

```promql
sum by (status) (rate(observability_http_requests_total[1m]))
```

and:

```promql
observability_readiness
```

In Grafana, open the provisioned **High Observability Dashboard** to inspect
request rate, average latency, and readiness.

## 6. Inspect a trace

Send a request and copy the `X-Trace-ID` response header:

```bash
curl -i http://localhost:8080/catalog
```

Open Jaeger at http://localhost:16686, select `catalog-service`, and run a trace
search. The trace represents the same request that also produced a log entry and
updated the metrics.

## What to observe

- **Liveness** reports whether the process is running.
- **Readiness** reports whether the application should receive traffic.
- **Metrics** expose aggregate runtime behavior over time.
- **Logs** provide detailed information about individual requests.
- **Trace IDs** correlate a request across observable signals.

The application exposes these signals externally, allowing its internal runtime
state to be understood without entering the container.

## Clean up

```bash
docker compose down -v
```
