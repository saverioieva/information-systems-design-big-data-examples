COMPOSE=docker compose
.PHONY: up logs approve decline invalid down reset test db adminer
up:
	$(COMPOSE) up -d --build
logs:
	$(COMPOSE) logs -f orchestrator consumer kitchen accounting
approve:
	curl -fsS -X POST http://localhost:8001/orders -H 'Content-Type: application/json' -d '{"customerId":"CUST_1","amount":42.0}'
decline:
	curl -fsS -X POST http://localhost:8001/orders -H 'Content-Type: application/json' -d '{"customerId":"CUST_1","amount":150.0}'
invalid:
	curl -fsS -X POST http://localhost:8001/orders -H 'Content-Type: application/json' -d '{"customerId":"CUST_INVALID","amount":42.0}'
test:
	python -m unittest discover -s tests -v
down:
	$(COMPOSE) down
reset:
	$(COMPOSE) down -v

# Simulate the first attempt failing for two post-pivot retriable commands.
.PHONY: retry ticket-failure history
retry:
	curl -fsS -X POST http://localhost:8001/orders -H 'Content-Type: application/json' -d '{"customerId":"CUST_1","amount":42.0,"simulateRetry":true}'
ticket-failure:
	curl -fsS -X POST http://localhost:8001/orders -H 'Content-Type: application/json' -d '{"customerId":"CUST_1","amount":42.0,"simulateTicketFailure":true}'
history:
	@test -n "$(ORDER_ID)" || (echo 'Use: make history ORDER_ID=<orderId>' && exit 1)
	curl -fsS http://localhost:8001/orders/$(ORDER_ID)/history

# Database inspections (Adminer or psql in each PostgreSQL container)
.PHONY: db-order db-consumer db-kitchen db-accounting
db-order:
	$(COMPOSE) exec postgres_order psql -U demo -d order_db
db-consumer:
	$(COMPOSE) exec postgres_consumer psql -U demo -d consumer_db
db-kitchen:
	$(COMPOSE) exec postgres_kitchen psql -U demo -d kitchen_db
db-accounting:
	$(COMPOSE) exec postgres_accounting psql -U demo -d accounting_db
