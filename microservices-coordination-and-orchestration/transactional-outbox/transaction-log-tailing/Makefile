COMPOSE = docker compose
.PHONY: up status create orders outbox received wal logs down reset test broker-pause broker-resume relay-restart relay-stop relay-start
up:
	$(COMPOSE) up -d --build
status:
	$(COMPOSE) ps
create:
	curl -fsS -X POST http://localhost:8004/orders -H 'Content-Type: application/json' -d '{"amount":42.0}'
orders:
	$(COMPOSE) exec -T postgres psql -U demo -d orders -c 'SELECT id, amount, status FROM orders;'
outbox:
	curl -fsS http://localhost:8004/outbox
received:
	curl -fsS http://localhost:8004/received
wal:
	$(COMPOSE) exec -T postgres psql -U demo -d orders -c 'SELECT slot_name, plugin, active, confirmed_flush_lsn, restart_lsn FROM pg_replication_slots;'
logs:
	$(COMPOSE) logs -f relay audit api
broker-pause:
	$(COMPOSE) stop rabbitmq
broker-resume:
	$(COMPOSE) start rabbitmq
relay-restart:
	$(COMPOSE) restart relay
relay-stop:
	$(COMPOSE) stop relay
relay-start:
	$(COMPOSE) start relay
test:
	python -m unittest discover -s tests -v
down:
	$(COMPOSE) down
reset:
	$(COMPOSE) down -v
