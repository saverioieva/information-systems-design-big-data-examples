# Verification and Classroom Readiness - Chapter 5

The project READMEs provide expected outputs, but full stack behavior depends on the local Docker runtime, available resources and connector readiness. The packaged Python code is not claimed to have passed a full Docker end-to-end test in this environment.

## Sanity checks by laboratory

| Lab | Unit tests | Main runtime checks |
|---|---|---|
| Kafka Fundamentals | `make test` | `make up`, `make partitions`, `make produce COUNT=12`, `make replay LIMIT=12` |
| CDC / Debezium | `make test` | `make up`, `make register`, `make status`, `make slots`, `make create`, `make raw COUNT=1`, `make integration COUNT=1`, `make audit` |
| Aggregate-Only | `make test` | `make up`, `make demo`, `make inspect` |
| Event-Sourced Orders | `make test`, `make test-integration` | `make up`, `make demo`, `make inspect`, `make inspect-snapshots`, `make idempotency-all` |

## Troubleshooting priorities

- **Kafka topic command prints usage:** inspect the Compose `topics` service's startup logs and the Kafka bootstrap address; confirm broker health before running client commands.
- **Debezium connectors fail registration:** run `make status` and inspect Kafka Connect logs; after `make up`, the Connect REST API must be healthy and PostgreSQL must have finished initialization.
- **No CDC messages:** verify publications, replication slots and topic names. `make raw` starts from the beginning and may return an earlier event first.
- **Unexpected duplicate RabbitMQ audit deliveries:** a bridge crash between publishing and Kafka offset commit can cause duplicates. The Audit Inbox should deduplicate by `eventId`.
- **No MongoDB in CDC:** intentional; MongoDB is present only as a standalone inbox backend in the Event-Sourced Orders idempotency comparison.
- **Unwanted stale state:** verify that the Aggregate-Only request carries the expected row version, whereas the Event-Sourced lab verifies the expected stream version.

Never reset databases or broker volumes before saving any demonstration data you intend to keep. `make reset` is intentionally destructive.
