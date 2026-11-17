# Order Persistence Comparison - Chapter 5

Two independent runnable examples compare **current-state SQL storage** and **Event Sourcing** for comparable `Order` business operations. Both have their own Docker Compose stack and Hexagonal application structure. The example on the left is **not** Event Sourcing; the example on the right uses the PostgreSQL `eventsourcing` library's append-only event store.

| Project | Core distinction | Main demo |
|---|---|---|
| [`01-aggregate-only/`](01-aggregate-only/) | PostgreSQL retains latest `orders` / `order_line_items` rows; version-checked updates | `make up && make demo && make inspect` |
| [`02-event-sourced-orders/`](02-event-sourced-orders/) | PostgreSQL event history is authoritative; state is rebuilt through replay | `make up && make demo && make inspect && make inspect-snapshots` |

The **PostgreSQL versus MongoDB idempotency** scenario is included only in [Example 02](02-event-sourced-orders/IDEMPOTENCY_POSTGRES_MONGODB.md), and does not make MongoDB the core Event Store. Use `make idempotency-all` from that example.

See the [Chapter 5 examples index](../README.md) for slide placement, setup order, architectural distinctions, and the Kafka/CDC examples. The DDD Aggregate and Unit of Work prerequisite remains in [Chapter 4](../../microservices-coordination-and-orchestration/ddd-aggregates/).
