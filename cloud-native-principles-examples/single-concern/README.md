# Single Concern: Init and Sidecar Containers

## Goal

Show how supporting work can be separated from the main application so each
container keeps one clear responsibility.

The example uses Docker Compose to model two common container patterns:

- an **init container** role prepares shared configuration and exits;
- a **sidecar** role runs next to the application and handles log forwarding.

Docker Compose calls the first component a one-shot service rather than an init
container, but its lifecycle in this example mirrors the same pattern used by
container orchestrators such as Kubernetes.

## 1. Start the example

```bash
cd single-concern
docker compose up -d --build
```

Inspect the services:

```bash
docker compose ps -a
```

`init` should be `Exited (0)`, while `app` and `sidecar` remain running.

## 2. Inspect the init container role

```bash
docker compose logs init
docker compose exec app cat /config/message.txt
```

The init service prepares `/config/message.txt` and the shared log file before
the main application starts.

## 3. Call the main application

```bash
curl -s http://localhost:8080/catalog
curl -s http://localhost:8080/catalog
```

The application serves the catalog and writes access records to the shared log
volume.

## 4. Inspect the sidecar role

```bash
docker compose logs sidecar
```

The sidecar reads the shared access log. The main application does not need to
implement log forwarding itself.

Generate more traffic and inspect the sidecar again:

```bash
for i in $(seq 1 3); do curl -s http://localhost:8080/catalog > /dev/null; done
docker compose logs --tail=10 sidecar
```

## What to observe

- The **init** component performs setup work once and then exits.
- The **app** container focuses on the catalog API.
- The **sidecar** performs a supporting runtime task without changing the app.
- Shared volumes provide explicit communication without merging responsibilities
  into one container.

## Clean up

```bash
docker compose down -v
```
