# Docker Architecture

This lab shows how Docker Compose builds an image, creates containers, connects
services through an internal network, and exposes the application through Nginx.
It does not demonstrate pushing an image to a remote registry.

## Build and inspect the image

```bash
cd architecture
docker compose build
docker image ls
docker compose images
```

## Start the containers

```bash
docker compose up -d
docker compose ps
```

Open http://localhost:8080 or run:

```bash
curl http://localhost:8080
```

The browser reaches `proxy`; the proxy reaches `app:80` through the Compose network.

Inspect the generated objects:

```bash
docker compose logs proxy
docker network ls
docker compose exec proxy wget -qO- http://app:80
```

## Clean up

```bash
docker compose down -v
```
