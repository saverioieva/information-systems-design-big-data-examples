COMPOSE = docker compose
BASE_URL ?= http://localhost:8003
PYTHON ?= python3
TEST_ENV = DATABASE_URL=sqlite+pysqlite:///:memory:
TEST_CONTAINER = $(COMPOSE) run --rm --no-deps -e DATABASE_URL=sqlite+pysqlite:///:memory: -v "$(CURDIR):/code" app python -m unittest

.PHONY: help up down reset status logs create approve demo events db test test-local test-domain test-entities test-value-objects test-invariants test-boundaries test-events test-api test-transactions test-image

help:
	@echo 'Start: make up | make status | make logs | make down | make reset'
	@echo 'Use:   make demo | make create | make approve ORDER_ID=<id> VERSION=<n> | make events | make db'
	@echo 'Test:  make test | make test-local | make test-domain | make test-api | make test-transactions'
	@echo '       make test-entities | make test-value-objects | make test-boundaries'
	@echo '       make test-invariants | make test-events'

up:
	$(COMPOSE) up -d --build

status:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f app

down:
	$(COMPOSE) down

reset:
	@echo 'WARNING: removes the PostgreSQL volume and ALL stored orders/outbox rows.'
	$(COMPOSE) down -v

create:
	curl -fsS -X POST $(BASE_URL)/orders -H 'Content-Type: application/json' -d '{"consumer_id":"CUST_1","restaurant_id":"REST_1","lines":[{"menu_item_id":"PIZZA","name":"Pizza","unit_price":{"amount":"10.00","currency":"EUR"},"quantity":2}]}'

approve:
	@test -n "$(ORDER_ID)" || (echo 'Usage: make approve ORDER_ID=<id> VERSION=<current-version> (set delivery address first)'; exit 1)
	curl -fsS -X POST "$(BASE_URL)/orders/$(ORDER_ID)/approve?expected_version=$(or $(VERSION),1)"

demo:
	BASE_URL=$(BASE_URL) $(PYTHON) -m examples.api_walkthrough

events:
	curl -fsS $(BASE_URL)/lab/outbox

db:
	$(COMPOSE) exec -T db psql -U ftgo -d ftgo -c 'SELECT event_type, aggregate_id, created_at FROM integration_outbox ORDER BY created_at'

test-image:
	$(COMPOSE) build app

test: test-image
	$(TEST_CONTAINER) discover -s tests -v

test-local:
	$(TEST_ENV) $(PYTHON) -m unittest discover -s tests -v

test-domain: test-image
	$(TEST_CONTAINER) tests.test_domain -v

test-entities: test-image
	$(TEST_CONTAINER) tests.test_domain.EntityTests -v

test-value-objects: test-image
	$(TEST_CONTAINER) tests.test_domain.ValueObjectTests -v

test-invariants: test-image
	$(TEST_CONTAINER) tests.test_domain.InvariantTests -v

test-boundaries: test-image
	$(TEST_CONTAINER) tests.test_domain.BoundaryTests -v

test-events: test-image
	$(TEST_CONTAINER) tests.test_domain.DomainEventTests -v

test-api: test-image
	$(TEST_CONTAINER) tests.test_api -v

test-transactions: test-image
	$(TEST_CONTAINER) tests.test_persistence -v
