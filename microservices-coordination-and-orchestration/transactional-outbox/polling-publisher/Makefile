COMPOSE=docker compose
.PHONY: up down reset logs create outbox received broker-pause broker-resume test
up:
	$(COMPOSE) up -d --build
logs:
	$(COMPOSE) logs -f api relay audit
create:
	curl -fsS -X POST http://localhost:8000/orders -H 'Content-Type: application/json' -d '{"amount":42.0}'
outbox:
	curl -fsS http://localhost:8000/outbox
received:
	curl -fsS http://localhost:8000/received
broker-pause:
	$(COMPOSE) stop rabbitmq
broker-resume:
	$(COMPOSE) start rabbitmq
test:
	python -m compileall -q app
down:
	$(COMPOSE) down
reset:
	$(COMPOSE) down -v
