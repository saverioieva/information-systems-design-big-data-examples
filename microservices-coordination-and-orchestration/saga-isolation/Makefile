COMPOSE=docker compose
.PHONY: up down reset logs status test approve decline invalid retry ticket-failure \
        unsafe semantic optimistic db-order db-consumer db-kitchen db-accounting

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

.PHONY: order history cancel-history gate release
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

db-order:
	$(COMPOSE) exec postgres_order psql -U demo -d order_db
db-consumer:
	$(COMPOSE) exec postgres_consumer psql -U demo -d consumer_db
db-kitchen:
	$(COMPOSE) exec postgres_kitchen psql -U demo -d kitchen_db
db-accounting:
	$(COMPOSE) exec postgres_accounting psql -U demo -d accounting_db
