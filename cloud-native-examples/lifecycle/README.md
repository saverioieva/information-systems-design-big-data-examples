# Lifecycle (Build → Run → Stop → Replace)

This lab demonstrates the **container lifecycle** using a tiny Docker-built web app behind a simple NGINX reverse proxy.

It is aligned with the **Container Lifecycle Management** concept in the slides (build → run/scale → replace/retire).  
Key idea: **containers are disposable runtime units** (not pets/servers).

---

## What you will run

- `web`: a minimal “app” image built from the local `Dockerfile` (serves `index.html`)
- `proxy`: NGINX reverse proxy exposing the app on `localhost:8080`

Folder contents:
- `Dockerfile` → builds the app image
- `index.html` → demo page returned by the app
- `docker-compose.yml` → defines app + proxy
- `nginx.conf` → routes traffic to `web` and supports scaling via DNS re-resolution

---

## 0) Start clean

```bash
cd lifecycle
docker compose down -v --remove-orphans
```

---

## 1) Build and run the stack

```bash
docker compose up -d --build
docker compose ps
```

### What you should see
- Docker builds `lifecycle-demo-app` from `Dockerfile`
- Two containers start: `lifecycle-web-1` and `lifecycle-proxy-1`

Verify:

```bash
docker compose ps
```

Open:
- http://localhost:8080

You should see the demo HTML page served by the `web` container.

---

## 2) Observe the lifecycle: stop / start / remove

Stop the app container only:

```bash
docker compose stop web
```

Now refresh http://localhost:8080  
You should see a **502 / Bad Gateway** (proxy is up, app is down).

Start it again:

```bash
docker compose start web
```

Refresh again: the page is back.

Remove and recreate `web` (replace container instance):

```bash
docker compose rm -f web
docker compose up -d web
```

### What this demonstrates
- Containers are **ephemeral**
- You can safely **replace** a container without changing the image definition

With one replica, stopping `web` intentionally causes an outage. Multiple healthy
replicas are required to preserve availability during replacement.

---

## 3) Scale horizontally

Scale `web` to 3 replicas:

```bash
docker compose up -d --scale web=3
```

Check running containers:

```bash
docker compose ps
```

### What this demonstrates
- **Horizontal scaling** by adding more instances of the same service
- `proxy` uses Docker DNS and periodically re-resolves `web` to include replicas

> Note: This is a Docker-level demo. In Kubernetes, the same concept is handled by Services + Deployments.

The `web` health check verifies that Nginx is serving the page. `depends_on`
controls startup sequencing in this lab; production systems also use readiness
checks before sending traffic to a new replica.

---

## 4) Tear down

```bash
docker compose down
```

If you also want to remove images built for the lab:

```bash
docker image rm lifecycle-demo-app:latest || true
```
