# Blue/Green Deployment — Docker Compose Lab

This lab demonstrates the **Blue/Green deployment** strategy using Docker Compose and an Nginx gateway.

Aligned with the course slides:
- two identical environments exist: **Blue (current production)** and **Green (new version candidate)**
- after validation, traffic is **flipped** from Blue to Green
- rollback is **instant**: flip back to Blue

---

## What is running in this lab

- `blue`: app version **BLUE**
- `green`: app version **GREEN**
- `proxy`: Nginx entrypoint at **http://localhost:8080**

Traffic routing is controlled by `nginx.conf` (the `upstream app { ... }` block).

---

## 0) Start clean

```bash
docker compose down -v --remove-orphans
```

---

## 1) Start both environments

Bring up **blue + green + proxy**:

```bash
docker compose up -d --build
```

Check:

```bash
docker compose ps
```

---

## 2) Route traffic to Blue (initial production)

Open `nginx.conf` and ensure the upstream points to **blue**:

```nginx
upstream app {
    server blue:5000;
    # server green:5000;
}
```

Reload Nginx inside the running proxy container:

```bash
docker compose exec proxy nginx -s reload
```

Validate:

```bash
for i in {1..5}; do curl -s http://localhost:8080; echo; done
```

Expected:
- responses identify **VERSION=BLUE**

---

## 3) Validate Green (pre-production)

Green is already running, but it is not receiving production traffic.
To validate it directly, you have two options:

### Option A — Temporarily switch traffic to Green

Edit `nginx.conf` to:

```nginx
upstream app {
    # server blue:5000;
    server green:5000;
}
```

Reload:

```bash
docker compose exec proxy nginx -s reload
```

Test:

```bash
curl -s http://localhost:8080
```

Expected:
- **VERSION=GREEN**

### Option B — Exec into the proxy and curl the service name

```bash
docker compose exec proxy wget -qO- http://green:5000
```

This test does not modify the running proxy container.

---

## 4) Traffic flip (go-live)

The go-live step **is the switch** in `nginx.conf` from Blue to Green + reload.

This represents the Blue/Green core property:
- **zero downtime**
- **instant cutover**

---

## 5) Instant rollback

If something is wrong with Green, rollback is simply:

- edit `nginx.conf` back to `server blue:5000;`
- reload Nginx:

```bash
docker compose exec proxy nginx -s reload
```

---

## Troubleshooting

View logs:

```bash
docker compose logs -f proxy
```

If you get a 502 after switching, wait a couple seconds and try again; the upstream may need a moment to become reachable.

---

## Clean up

```bash
docker compose down -v
```
