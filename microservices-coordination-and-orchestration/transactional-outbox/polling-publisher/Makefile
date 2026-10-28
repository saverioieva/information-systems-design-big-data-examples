COMPOSE=docker compose
.PHONY: up down reset logs status create outbox received broker-pause broker-resume test
up:
	$(COMPOSE) up -d --build --remove-orphans
status:
	$(COMPOSE) ps
logs:
	$(COMPOSE) logs -f api relay audit
create:
	curl -fsS -X POST http://localhost:8000/orders -H 'Content-Type: application/json' -d '{"amount":42.0}'
outbox:
	curl -fsS http://localhost:8000/outbox
received:
	$(COMPOSE) exec -T postgres_audit psql -U demo -d audit -c 'SELECT event_id, aggregate_id, received_at FROM received_events ORDER BY received_at DESC;' 
broker-pause:
	$(COMPOSE) stop rabbitmq
broker-resume:
	$(COMPOSE) start rabbitmq
test:
	python -m compileall -q app
	python -m unittest discover -s tests -v
down:
	$(COMPOSE) down --remove-orphans
reset:
	$(COMPOSE) down -v --remove-orphans
