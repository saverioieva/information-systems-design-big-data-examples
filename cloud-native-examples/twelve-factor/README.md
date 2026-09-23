# Twelve-Factor Mini Lab

This lab revisits selected Twelve-Factor principles after the Docker and Docker
Compose introduction. One small Flask application and Redis backing service
make the principles observable without creating twelve separate exercises.

## Factors demonstrated

| Factor | Evidence in the lab |
|---|---|
| Dependencies | `requirements.txt` declares Flask and Redis |
| Config | `APP_MESSAGE`, `APP_ENV`, and `REDIS_HOST` come from environment variables |
| Backing services | Redis is attached through its service hostname |
| Build, release, run | Docker builds the image; Compose supplies release configuration and runs it |
| Processes | The Flask process stores no visit state locally |
| Port binding | Flask binds to port 5000 and Compose publishes it as port 8080 |
| Disposability | Replacing the app container does not lose the Redis counter |
| Logs | The application writes request events to stdout |
| Admin processes | `admin.py` runs as a one-off process in the same image |

Codebase, Concurrency, and Dev/Prod Parity remain discussion topics in this
introductory lab.

## 1. Build and run

From a Bash-compatible terminal:

```bash
cd twelve-factor
export APP_MESSAGE="Hello from staging"
export APP_ENV="staging"
docker compose up -d --build
docker compose ps
```

Open http://localhost:8080 or run:

```bash
curl http://localhost:8080
curl http://localhost:8080
```

The message and environment come from configuration. The visit number is stored
in Redis.

## 2. Observe logs as an event stream

```bash
docker compose logs app
```

The application writes request events to stdout. Docker captures the stream;
the application does not manage log files.

## 3. Replace the stateless process

```bash
docker compose rm -sf app
docker compose up -d app
curl http://localhost:8080
```

The visit count continues because Redis owns the persistent state.

## 4. Run an admin process

```bash
docker compose run --rm app python admin.py
```

The one-off command uses the same image, dependencies, and environment as the
web process.

## 5. Compare release configurations

Change only the environment variables and recreate the application:

```bash
export APP_MESSAGE="Hello from production"
export APP_ENV="production"
docker compose up -d --force-recreate app
curl http://localhost:8080
```

The image and source code remain unchanged while the release configuration changes.

## Clean up

```bash
docker compose down -v
unset APP_MESSAGE APP_ENV
```
