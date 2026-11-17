COMPOSE=docker compose
.PHONY: up down reset logs status test approve decline invalid retry ticket-failure \
        unsafe semantic optimistic reread pessimistic by-value commutative version-file db-order db-consumer db-kitchen db-accounting

up:
	$(COMPOSE) up -d --build
status:
	$(COMPOSE) ps
logs:
	$(COMPOSE) logs -f orchestrator consumer kitchen accounting
down:
	$(COMPOSE) down
reset:
	$(COMPOSE) down -v
test:
	python3 -m unittest discover -s tests -v

# Original CreateOrder Saga (unchanged behavior).
approve:
	curl -fsS -X POST http://localhost:8001/orders -H 'Content-Type: application/json' -d '{"customerId":"CUST_1","amount":42}'
decline:
	curl -fsS -X POST http://localhost:8001/orders -H 'Content-Type: application/json' -d '{"customerId":"CUST_1","amount":150}'
invalid:
	curl -fsS -X POST http://localhost:8001/orders -H 'Content-Type: application/json' -d '{"customerId":"CUST_INVALID","amount":42}'
retry:
	curl -fsS -X POST http://localhost:8001/orders -H 'Content-Type: application/json' -d '{"customerId":"CUST_1","amount":42,"simulateRetry":true}'
ticket-failure:
	curl -fsS -X POST http://localhost:8001/orders -H 'Content-Type: application/json' -d '{"customerId":"CUST_1","amount":42,"simulateTicketFailure":true}'

# End-to-end scenarios: Python stdlib client, real RabbitMQ and 4 real PostgreSQLs.
unsafe:
	python3 demo/run_scenario.py unsafe
semantic:
	python3 demo/run_scenario.py semantic
optimistic:
	python3 demo/run_scenario.py optimistic
reread:
	python3 demo/run_scenario.py reread
pessimistic:
	python3 demo/run_scenario.py pessimistic
by-value:
	python3 demo/run_scenario.py by_value
# Distributed countermeasure workflows: REST -> Order Outbox -> RabbitMQ -> participants.
commutative:
	python3 demo/run_countermeasure.py commutative
version-file:
	python3 demo/run_countermeasure.py version-file

.PHONY: order history cancel-history gate release cancel-gate release-cancel
order:
	@test -n "$(ORDER_ID)" || (echo 'Use ORDER_ID=<id>' && exit 1)
	curl -fsS http://localhost:8001/orders/$(ORDER_ID)
history:
	@test -n "$(ORDER_ID)" || (echo 'Use ORDER_ID=<id>' && exit 1)
	curl -fsS http://localhost:8001/orders/$(ORDER_ID)/history
cancel-history:
	@test -n "$(ORDER_ID)" || (echo 'Use ORDER_ID=<id>' && exit 1)
	curl -fsS http://localhost:8001/orders/$(ORDER_ID)/cancel/history
gate:
	@test -n "$(ORDER_ID)" || (echo 'Use ORDER_ID=<id>' && exit 1)
	curl -fsS http://localhost:8001/orders/$(ORDER_ID)/gate
release:
	@test -n "$(ORDER_ID)" || (echo 'Use ORDER_ID=<id>' && exit 1)
	curl -fsS -X POST http://localhost:8001/orders/$(ORDER_ID)/release
cancel-gate:
	@test -n "$(ORDER_ID)" || (echo 'Use ORDER_ID=<id>' && exit 1)
	curl -fsS http://localhost:8001/orders/$(ORDER_ID)/cancel/gate
release-cancel:
	@test -n "$(ORDER_ID)" || (echo 'Use ORDER_ID=<id>' && exit 1)
	curl -fsS -X POST http://localhost:8001/orders/$(ORDER_ID)/cancel/release

db-order:
	$(COMPOSE) exec postgres_order psql -U demo -d order_db
db-consumer:
	$(COMPOSE) exec postgres_consumer psql -U demo -d consumer_db
db-kitchen:
	$(COMPOSE) exec postgres_kitchen psql -U demo -d kitchen_db
db-accounting:
	$(COMPOSE) exec postgres_accounting psql -U demo -d accounting_db

# Complete scenario suite: automatic, with no interactive steps.
# Test-only Outbox message holds make races reproducible; they are not isolation controls.
.PHONY: demo demo-saga demo-extra verify

demo:
	@printf '\n%s\n' '=== Unsafe baseline: stale approval anomaly ==='
	python3 demo/run_scenario.py unsafe --summary
	@printf '\n%s\n' '=== Semantic Lock ==='
	python3 demo/run_scenario.py semantic --summary
	@printf '\n%s\n' '=== Pessimistic View ==='
	python3 demo/run_scenario.py pessimistic --summary
	@printf '\n%s\n' '=== Commutative Updates ==='
	$(MAKE) commutative
	@printf '\n%s\n' '=== Reread Value ==='
	python3 demo/run_scenario.py reread --summary
	@printf '\n%s\n' '=== Version Check ==='
	python3 demo/run_scenario.py optimistic --summary
	@printf '\n%s\n' '=== Version File ==='
	$(MAKE) version-file
	@printf '\n%s\n' '=== By Value ==='
	python3 demo/run_scenario.py by_value --summary

demo-saga:
	python3 demo/run_scenario.py unsafe --summary
	python3 demo/run_scenario.py semantic --summary
	python3 demo/run_scenario.py pessimistic --summary
	python3 demo/run_scenario.py reread --summary
	python3 demo/run_scenario.py optimistic --summary
	python3 demo/run_scenario.py by_value --summary

demo-extra:
	$(MAKE) commutative
	$(MAKE) version-file

verify:
	python3 -m compileall -q app demo tests
	python3 -m unittest discover -s tests -v

.PHONY: help
help:
	@printf '%s\n' \
	  'Saga Isolation examples (automated, no interactive prompts):' \
	  '  make up                Start RabbitMQ, four PostgreSQL services, APIs' \
	  '  make demo              Run ALL the examples automatically' \
	  '  make demo-saga         Run competing-Saga examples' \
	  '  make demo-extra        Run distributed credit and Version File workflows' \
	  '  make unsafe            Reproduce a lost update' \
	  '  make semantic          Semantic lock + sequential cancellation' \
	  '  make pessimistic       Pending -> Kitchen pivot -> CANCELLED -> Accounting void' \
	  '  make commutative       REST/RabbitMQ Consumer + Accounting credit sagas' \
	  '  make reread            Reread Value with atomic status check' \
	  '  make optimistic        Optimistic locking with version check' \
	  '  make version-file      REST/RabbitMQ Consumer + Kitchen reordering' \
	  '  make by-value          Choose policy using order amount' \
	  '  make test / make verify   Unit and optional Postgres tests' \
	  '  make down              Stop containers and keep DB data' \
	  '  make reset             DANGER: delete all persistent DB volumes'
