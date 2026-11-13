COMPOSE=docker compose
KAFKA=$(COMPOSE) exec -T kafka /opt/kafka/bin
.PHONY: up register status create orders outbox raw integration approve db-update kafka-topics rabbit-queues audit poison dlq slots logs test down reset
up:
	$(COMPOSE) up -d --build
register:
	python3 scripts/register_connectors.py register
status:
	$(COMPOSE) ps
	python3 scripts/register_connectors.py status
create:
	curl -fsS -X POST http://localhost:8004/orders -H 'Content-Type: application/json' -d '{"amount":42.50}'
approve:
	@test -n "$(ORDER_ID)" || (echo 'Usage: make approve ORDER_ID=<id>'; exit 1)
	curl -fsS -X POST "http://localhost:8004/orders/$(ORDER_ID)/approve"
orders:
	curl -fsS http://localhost:8004/orders
outbox:
	curl -fsS http://localhost:8004/outbox
raw:
	$(KAFKA)/kafka-console-consumer.sh --bootstrap-server kafka:19092 --topic cdc_orders.public.orders --from-beginning --max-messages $(or $(COUNT),1) --timeout-ms 15000
integration:
	$(KAFKA)/kafka-console-consumer.sh --bootstrap-server kafka:19092 --topic orders.integration --from-beginning --max-messages $(or $(COUNT),1) --timeout-ms 15000
db-update:
	$(COMPOSE) exec -T postgres psql -U demo -d orders -c "UPDATE orders SET status='APPROVED' WHERE id=(SELECT id FROM orders WHERE status='CREATED' ORDER BY created_at DESC LIMIT 1);"
kafka-topics:
	$(KAFKA)/kafka-topics.sh --bootstrap-server kafka:19092 --list
audit:
	$(COMPOSE) exec -T audit python -m audit.main --list
poison:
	$(COMPOSE) exec -T audit python -m audit.main --poison
dlq:
	$(COMPOSE) exec -T rabbitmq rabbitmqctl list_queues name messages_ready consumers
slots:
	$(COMPOSE) exec -T postgres psql -U demo -d orders -c 'SELECT slot_name, plugin, active, restart_lsn FROM pg_replication_slots'
logs:
	$(COMPOSE) logs -f api connect bridge audit
test:
	python3 -m unittest discover -s tests -v
down:
	$(COMPOSE) down
reset:
	$(COMPOSE) down -v
