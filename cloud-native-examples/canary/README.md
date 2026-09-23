# Canary Deployment — Docker Compose Lab

This lab demonstrates a **Canary deployment** using Docker Compose and an Nginx gateway.

Aligned with the course slides:
- a **stable** version serves most users
- a **canary** version is exposed to a **small percentage** of traffic
- if metrics and user feedback are good, you **increase traffic** to canary gradually
- if something goes wrong, you route all traffic back to stable

---

## What is running in this lab

- `stable`: app version **STABLE**
- `canary`: app version **CANARY**
- `proxy`: Nginx entrypoint at **http://localhost:8080**

Traffic split is controlled by `nginx.conf` via upstream weights.

---

## 0) Start clean

```bash
docker compose down -v --remove-orphans
```

---

## 1) Start the lab

```bash
docker compose up -d --build
```

Open:
- http://localhost:8080

---

## 2) Observe the traffic split (stable vs canary)

Send many requests and count how often you hit CANARY:

```bash
for i in {1..50}; do curl -s http://localhost:8080; echo; done
```

Expected (with the default config):
- most responses show **VERSION=STABLE**
- a few responses show **VERSION=CANARY**

To summarize a larger sample:

```bash
for i in $(seq 1 100); do curl -s http://localhost:8080; echo; done | sort | uniq -c
```

---

## 3) How the split works (weights)

Open `nginx.conf` and look at the upstream:

```nginx
upstream app {
    server stable:5000 weight=9;
    server canary:5000 weight=1;
}
```

Interpretation:
- Stable gets ~90% of requests
- Canary gets ~10% of requests

> Important: This is **probabilistic**, not exact per N requests.

This lab demonstrates weighted traffic routing. A production canary also needs
health metrics, error thresholds, and an automated promotion or rollback policy.

After editing `nginx.conf`, reload Nginx inside the running proxy container:

```bash
docker compose exec proxy nginx -s reload
```

---

## 4) Increase canary traffic (progressive rollout)

### Step A — 25% canary

Edit `nginx.conf` to:

```nginx
upstream app {
    server stable:5000 weight=3;
    server canary:5000 weight=1;
}
```

Reload:

```bash
docker compose exec proxy nginx -s reload
```

Verify:

```bash
for i in {1..40}; do curl -s http://localhost:8080; echo; done
```

### Step B — 50% canary

```nginx
upstream app {
    server stable:5000 weight=1;
    server canary:5000 weight=1;
}
```

Reload and test again.

### Step C — 100% canary (promotion)

```nginx
upstream app {
    server canary:5000;
    # server stable:5000;
}
```

At this point, canary is effectively the new stable.

---

## 5) Instant rollback

If the canary misbehaves, rollback is immediate:

```nginx
upstream app {
    server stable:5000;
    # server canary:5000;
}
```

Reload:

```bash
docker compose exec proxy nginx -s reload
```

---

## Troubleshooting

See container status:

```bash
docker compose ps
```

Follow logs:

```bash
docker compose logs -f proxy
```

If you get a 502, wait a moment and retry (upstreams might still be starting).

---

## Clean up

```bash
docker compose down -v
```
