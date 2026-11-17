.PHONY: up down logs demo test test-integration inspect inspect-snapshots idempotency-postgres idempotency-mongo idempotency-all reset
up:
	docker compose up -d --build db orders-es

down:
	docker compose down

logs:
	docker compose logs -f orders-es

demo:
	python3 scripts/demo.py

test:
	docker compose run --rm --build orders-es-tests

test-integration:
	docker compose run --rm --build orders-es-integration-tests

inspect:
	docker compose exec -T db psql -U eventsourcing -d orders_es -c 'SELECT originator_id,originator_version,topic FROM orderapplication_events ORDER BY originator_id,originator_version LIMIT 20;'

inspect-snapshots:
	docker compose exec -T db psql -U eventsourcing -d orders_es -c 'SELECT originator_id,originator_version FROM orderapplication_snapshots ORDER BY originator_id,originator_version LIMIT 20;'

idempotency-postgres:
	docker compose up -d --wait db
	docker compose run --rm --build --no-deps idempotency-demo python -m idempotency.demo --backend postgres

idempotency-mongo:
	docker compose up -d --wait mongo
	docker compose run --rm --build --no-deps idempotency-demo python -m idempotency.demo --backend mongo

idempotency-all: idempotency-postgres idempotency-mongo

reset:
	docker compose down -v
