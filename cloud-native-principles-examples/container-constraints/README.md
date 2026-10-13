# Container Constraints

## Goal

Inspect container runtime constraints and observe how a container reacts to
lifecycle signals such as `SIGTERM`.

The example demonstrates:

- running the application as a **non-root user**;
- using a **read-only root filesystem**;
- allowing writes only in explicitly writable locations such as `/tmp`;
- dropping unnecessary Linux capabilities;
- defining explicit **CPU, memory, and PID limits**;
- handling graceful shutdown.

## 1. Start the container and inspect security constraints

```bash
cd container-constraints
unset APP_MESSAGE
docker compose up -d --build
curl -s http://localhost:8080/
```

The container is configured with restricted privileges and filesystem access.

### Check the runtime user

```bash
docker compose exec app id
```

The application should run as a **non-root user** rather than as `root`.

This reduces the privileges available to the process if the application is
compromised.

### Verify that the application filesystem is read-only

```bash
docker compose exec app sh -c 'echo x > /app/test.txt'
```

This command should fail because the container root filesystem is configured as
**read-only**.

The application therefore cannot modify its own code or create arbitrary files
under `/app` at runtime.

### Verify that temporary storage is writable

```bash
docker compose exec app sh -c 'echo x > /tmp/test.txt && cat /tmp/test.txt'
```

This command should succeed and print:

```text
x
```

Although the root filesystem is read-only, `/tmp` is explicitly provided as a
temporary writable filesystem.

The resulting confinement model is:

```text
Application process  -> non-root user

/app                 -> read-only
/tmp                 -> writable temporary storage
```

This follows the **least privilege** principle: the container receives only the
permissions and writable storage that it actually needs.

## 2. Change configuration without rebuilding the image

```bash
export APP_MESSAGE="Hello from configuration"
docker compose up -d --force-recreate app
curl -s http://localhost:8080/
```

The same container image now runs with a different environment value.

This shows that runtime configuration can change independently from the
container image.

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

Docker first sends `SIGTERM`.

The application handles the signal, allows the current request to finish, and
then shuts down gracefully.

Compare this with a shorter grace period:

```bash
docker compose start app
```

Start `/slow` again in terminal A, then run:

```bash
docker compose stop -t 1 app
```

If the application does not terminate within the one-second grace period,
Docker may forcefully terminate it with `SIGKILL`.

Conceptually:

```text
docker stop
    |
    v
 SIGTERM
    |
    | grace period
    v
application exits?
    |
   yes -> graceful shutdown
    |
    no
    v
 SIGKILL
```

## 4. Inspect resource limits

```bash
docker compose start app

docker inspect "$(docker compose ps -q app)" \
  --format '{{.HostConfig.Memory}} {{.HostConfig.NanoCpus}} {{.HostConfig.PidsLimit}}'

docker stats --no-stream
```

The configured limits are:

```text
Memory -> 128 MiB
CPU    -> 0.5 CPU
PIDs   -> 64
```

Docker internally represents CPU limits using `NanoCpus`.

For example:

```text
0.5 CPU = 500000000 NanoCpus
```

CPU and memory constraints behave differently.

If the CPU limit is reached:

```text
CPU limit reached
    |
    v
CPU throttling
    |
    v
application becomes slower
```

If the memory limit is exceeded:

```text
Memory limit exceeded
    |
    v
OOM condition
    |
    v
process terminated
    |
    v
SIGKILL / exit code 137
```

## What to observe

- The application runs as a **non-root user**.
- The normal container filesystem is **read-only**.
- Only explicitly configured paths such as `/tmp` are writable.
- Containers should react correctly to lifecycle signals.
- Graceful shutdown requires enough time for in-flight work to complete.
- CPU, memory, PID, filesystem, and privilege constraints should be explicit.

## Clean up

```bash
unset APP_MESSAGE
docker compose down -v
```
