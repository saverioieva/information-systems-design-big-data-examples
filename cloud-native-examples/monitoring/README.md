# Monitoring with Prometheus and Grafana

## Goal

Observe application request counters and latency metrics outside the application
container.

## Architecture

- `app` exposes `/metrics` in Prometheus format
- Prometheus scrapes `app:5000/metrics`
- Grafana queries Prometheus and displays the supplied dashboard

This lab focuses on **metrics**. Centralized logging is discussed theoretically
in the slides and is outside the scope of this introductory exercise.

## Start

```bash
cd monitoring
docker compose up -d --build
docker compose ps
```

Open:

- Application: http://localhost:5000
- Raw metrics: http://localhost:5000/metrics
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000

Grafana credentials:

```text
username: admin
password: admin
```

## Generate traffic

```bash
for i in $(seq 1 20); do curl -s http://localhost:5000 > /dev/null; done
```

In Prometheus, try:

```promql
rate(flask_http_request_total[1m])
```

In Grafana, open the provisioned **Flask App Dashboard**. Request rate and
average latency should change after new traffic.

## Clean up

```bash
docker compose down -v
```
