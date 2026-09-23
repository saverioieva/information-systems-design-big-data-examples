# PaaS Responsibility Analogy

The student edits only `app/app.py`. The Compose definition supplies the Python
runtime and starts the application, similar to a small platform contract.

> This is a local analogy. A real PaaS hides more infrastructure and normally
> provides managed build, deployment, scaling, and logging features.

## Start the application

```bash
cd service-models/paas
docker compose up -d
docker compose ps
curl http://localhost:8080
```

## Change the code

Edit the message returned by `app/app.py`, then restart the application:

```bash
docker compose restart app
curl http://localhost:8080
```

No Dockerfile or operating-system administration is required in this lab. The
platform definition selects the runtime and exposes the application.

## Clean up

```bash
docker compose down -v
```
