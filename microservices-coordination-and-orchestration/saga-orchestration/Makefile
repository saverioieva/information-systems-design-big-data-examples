COMPOSE=docker compose
.PHONY: up logs approve decline invalid down reset test
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
