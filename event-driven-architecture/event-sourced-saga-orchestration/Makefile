.PHONY: adminer up down reset logs test demo-happy demo-compensation demo-recovery inspect inspect-order inspect-accounting inspect-kitchen inspect-saga
up:
	docker compose up -d --build --wait order accounting kitchen orchestrator

adminer:
	docker compose up -d adminer
	@echo "Adminer: http://localhost:8183 (PostgreSQL: server order-db, accounting-db, kitchen-db, or saga-db; database events; user/password demo)"

down:
	docker compose down

reset:
	docker compose down -v

logs:
	docker compose logs -f order accounting kitchen orchestrator

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
