# SaaS Responsibility Analogy

Adminer is a ready-made database administration application. Students use its
web interface without writing or building the application code.

> Docker keeps the exercise local. In real SaaS, the provider would also run,
> update, secure, and scale the application and its infrastructure.

## Start the ready-made application

```bash
cd service-models/saas
docker compose up -d
docker compose ps
```

Open http://localhost:8080 and log in with:

```text
System: PostgreSQL
Server: database
Username: student
Password: student
Database: course
```

These credentials are intentionally simple for a local classroom lab. Do not
reuse them in any deployed environment.

Create a table or inspect the database from the web interface. You configure and
use the product, but you do not change its source code.

## Clean up

```bash
docker compose down -v
```
