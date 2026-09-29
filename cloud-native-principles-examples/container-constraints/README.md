# Container Constraints

## Goal

Inspect container runtime limits and observe graceful shutdown when Docker sends
`SIGTERM`.

The example uses a non-root user, a read-only filesystem, dropped capabilities,
and explicit CPU, memory, and PID limits.

## 1. Start the container

```bash
cd container-constraints
unset APP_MESSAGE
docker compose up -d --build
curl -s http://localhost:8080/
```

Inspect the runtime identity and filesystem:

```bash
docker compose exec app id
docker compose exec app sh -c 'echo x > /app/test.txt'
docker compose exec app sh -c 'echo x > /tmp/test.txt && cat /tmp/test.txt'
```

Writing under `/app` fails because the root filesystem is read-only. `/tmp` is
available through a temporary filesystem.

## 2. Change configuration without rebuilding the image

```bash
export APP_MESSAGE="Hello from configuration"
docker compose up -d --force-recreate app
curl -s http://localhost:8080/
```

The same image runs with a different environment value.

## 3. Observe graceful shutdown

In terminal A:

```bash
curl -s http://localhost:8080/slow
```

While the request is running, use terminal B:

```bash
docker compose logs --tail=5 app
docker compose stop app
docker compose logs --tail=10 app
```

The application receives `SIGTERM`, lets the current request finish, and then
shuts down.

Compare it with a shorter grace period:

```bash
docker compose start app
# Start /slow again in terminal A, then run:
docker compose stop -t 1 app
```

Docker may send `SIGKILL` before the slow request can finish.

## 4. Inspect resource limits

```bash
docker compose start app
docker inspect "$(docker compose ps -q app)" \
  --format '{{.HostConfig.Memory}} {{.HostConfig.NanoCpus}} {{.HostConfig.PidsLimit}}'
docker stats --no-stream
```

The configured limits are 128 MiB memory, 0.5 CPU, and 64 PIDs.

## What to observe

- Containers should react correctly to lifecycle signals.
- Graceful shutdown requires enough time for in-flight work.
- Runtime resource and security constraints should be explicit.

## Clean up

```bash
unset APP_MESSAGE
docker compose down -v
```
