# Rolling Deployment (Real Rolling Update with Compose)

This lab demonstrates a **real rolling update** using Docker Compose:

- **One service name** (`web`)
- **Multiple replicas** (`--scale web=N`)
- Update is performed by **replacing replicas one-by-one**, while the other replicas remain active

> In Kubernetes, a Deployment controller does this automatically.
> With Docker Compose, we simulate the same behavior **explicitly**, to make the mechanism visible.

---

## Architecture

- **proxy** (nginx) listens on `localhost:8080`
- **web** is the application service, running **multiple replicas**
- nginx routes to `web` by DNS name; Docker’s internal DNS load-balances across replicas

---

## What You Will Observe

- With 3 replicas, repeated requests will show **different hostnames** → load balancing is working.
- During the rollout, you will see a **mix of v1 and v2** for a short time.
- After the rollout, you will only see **v2**.

---

## 1) Start v1 with 3 replicas

From this folder:

```bash
export APP_VERSION=v1
docker compose up -d --build --scale web=3
```

Test (you should see v1 + different hostnames):

```bash
for i in $(seq 1 10); do curl -s localhost:8080; done
```

Example output:

```
Hello from v1 | host=web-1
Hello from v1 | host=web-2
Hello from v1 | host=web-3
```

---

## 2) Build v2 (IMPORTANT: build only)

Now build the new version **without changing the service definition**.

We keep the image tag constant (`rolling-web:prod`) so Compose does **not** decide to recreate every container.

```bash
export APP_VERSION=v2
docker compose build web
```

At this point:
- existing replicas are still running v1 (old image ID)
- the tag `rolling-web:prod` now points to the new v2 image

---

## 3) Rolling update: replace replicas one-by-one

Use the supplied script so that only replicas using the previous image ID are
selected for replacement:

```bash
export REPLICAS=3
sh ./rollout_one_by_one.sh
```

The script identifies replicas that still use the previous image ID. It does
not rely on container ordering when choosing the next replica to replace.

While the script runs, use another terminal to observe the temporary mixture:

```bash
for i in $(seq 1 12); do curl -s localhost:8080; done
```

After the final replacement, every response should report `v2`.

---

## Rollback (same mechanism)

Build v1 again:

```bash
export APP_VERSION=v1
docker compose build web
```

Then run `sh ./rollout_one_by_one.sh` again.
That rolls you back gradually while the other replicas remain active.

This classroom script preserves running replicas while a replacement starts.
Production orchestrators additionally wait for readiness checks before continuing.

---

## Clean up

```bash
docker compose down
```
