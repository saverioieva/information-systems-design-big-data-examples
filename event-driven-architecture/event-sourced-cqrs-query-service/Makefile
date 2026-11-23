.PHONY: up down reset logs test demo-happy demo-compensation demo-recovery demo-comparison demo-outage demo-catchup rebuild-projection inspect inspect-order inspect-accounting inspect-kitchen inspect-saga inspect-query
up:
	docker compose up -d --build --wait order accounting kitchen orchestrator query

down:
	docker compose down

reset:
	docker compose down -v

logs:
	docker compose logs -f order accounting kitchen orchestrator query

test:
	docker compose run --rm --build --no-deps unit-tests

demo-happy:
	docker compose run --rm --no-deps --build demo --scenario happy

demo-compensation:
	docker compose run --rm --no-deps --build demo --scenario compensation

demo-recovery:
	@set -e; trap 'docker compose start accounting >/dev/null' EXIT; \
	 docker compose stop accounting; \
	 docker compose run --rm --no-deps --build demo --scenario create-only; \
	 docker compose run --rm --no-deps demo --scenario wait-started; \
	 docker compose restart orchestrator; \
	 docker compose start accounting; \
	 docker compose run --rm --no-deps demo --scenario show-last

inspect:
	@for service in order accounting kitchen orchestrator; do docker compose exec -T $$service python -c 'from lab.storage import EventStore; print(EventStore().stats())'; done

inspect-order:
	docker compose exec -T order-db psql -U demo -d events -c "SELECT aggregate_id,version,event_type,payload FROM events ORDER BY occurred_at,version LIMIT 30"

inspect-accounting:
	docker compose exec -T accounting-db psql -U demo -d events -c "SELECT aggregate_id,version,event_type,payload FROM events ORDER BY occurred_at,version LIMIT 30"

inspect-kitchen:
	docker compose exec -T kitchen-db psql -U demo -d events -c "SELECT aggregate_id,version,event_type,payload FROM events ORDER BY occurred_at,version LIMIT 30"

inspect-saga:
	docker compose exec -T saga-db psql -U demo -d events -c "SELECT aggregate_id,version,event_type,payload FROM events ORDER BY occurred_at,version LIMIT 40"

# The comparison is executed from the demo container on the same Docker network.
demo-comparison:
	docker compose run --rm --no-deps --entrypoint python demo -m scripts.compare --scenario compare

# The demo starts with a completed order; only composition needs the three APIs.
demo-outage:
	docker compose run --rm --no-deps --entrypoint python demo -m scripts.compare --scenario compare
	@trap 'docker compose start kitchen >/dev/null' EXIT; \
	 docker compose stop kitchen; \
	 docker compose run --rm --no-deps --entrypoint python demo -m scripts.compare --scenario compare-last

# The durable query queue buffers integration events while the query service is down.
demo-catchup:
	docker compose stop query
	docker compose run --rm --no-deps demo --scenario create-only
	docker compose start query
	docker compose run --rm --no-deps --entrypoint python demo -m scripts.compare --scenario compare-last

rebuild-projection:
	docker compose run --rm --no-deps --entrypoint python demo -m scripts.compare --scenario rebuild

inspect-query:
	docker compose exec -T query-db psql -U demo -d events -c "SELECT order_id,order_status,payment_status,kitchen_status FROM order_summary ORDER BY updated_at DESC LIMIT 20"
	docker compose exec -T query-db psql -U demo -d events -c "SELECT order_id,source,last_version FROM projection_offsets ORDER BY order_id,source"
