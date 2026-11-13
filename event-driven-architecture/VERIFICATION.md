# Verification and first-run checklist

Static and offline checks completed when packaging this block:

- `make test-local`: 23 passing tests across three labs (12 DDD + 3 Kafka Fundamentals + 8 CDC/bridge/audit).
- YAML parsing: all three Docker Compose configurations; service dependencies and host-port collisions checked.
- JSON parsing: both Debezium Kafka Connect connector configurations.
- Python syntax compilation: all `.py` files.
- DDD SQL transaction test using an in-memory SQLite test database verifies that an outbox insertion failure rolls back the corresponding Order write.
- Kafka/RabbitMQ routing and local Audit Inbox duplicate detection tested without brokers.

**Docker was not available in the authoring environment.** Container startup, actual PostgreSQL logical replication, Kafka Connect behavior, Kafka-to-RabbitMQ forwarding, and real AMQP dead-letter routing remain to be confirmed on a machine with Docker before classroom delivery.

## Suggested first-run smoke test

```bash
cd kafka-fundamentals
make up
make produce COUNT=12
make partitions
make replay LIMIT=12
make down

cd ../cdc-debezium-rabbitmq
make up
make register
make status
make create
make raw COUNT=1
make integration COUNT=1
make audit
make slots
make poison
make dlq
make down
```

When experimenting with connector problems, check `docker compose logs connect` and then `make slots` before deleting volumes. `make reset` is destructive. Confirm that the bridge and audit print the same `eventId` and that the `audit.orders.dlq` message count increases after `make poison`.
