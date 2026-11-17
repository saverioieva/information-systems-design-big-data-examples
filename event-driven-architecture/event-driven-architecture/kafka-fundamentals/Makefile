COMPOSE=docker compose
KAFKA=$(COMPOSE) exec -T kafka /opt/kafka/bin
.PHONY: up status down reset logs topics partitions produce consume replay worker groups group-info test ui
up:
	$(COMPOSE) up -d kafka kafka-ui
	$(COMPOSE) run --rm topics
	$(COMPOSE) build client
status:
	$(COMPOSE) ps
ui:
	$(COMPOSE) up -d kafka-ui
	@echo "Kafka UI: http://localhost:8085"
topics:
	$(KAFKA)/kafka-topics.sh --bootstrap-server kafka:19092 --list
partitions:
	$(KAFKA)/kafka-topics.sh --bootstrap-server kafka:19092 --describe --topic orders.events
produce:
	$(COMPOSE) run --rm client python -m app.main produce --count $(or $(COUNT),12) --prefix $(or $(PREFIX),DEMO)
consume:
	$(COMPOSE) run --rm client python -m app.main consume --group order-processors --limit $(or $(LIMIT),12) --idle 12
replay:
	$(COMPOSE) run --rm client python -m app.main consume --group replay-$(shell date +%s) --limit $(or $(LIMIT),12) --idle 12
worker:
	$(COMPOSE) run --rm client python -m app.main consume --group $(or $(GROUP),shared-workers) --limit 0 --idle 0
groups:
	$(KAFKA)/kafka-consumer-groups.sh --bootstrap-server kafka:19092 --list
group-info:
	$(KAFKA)/kafka-consumer-groups.sh --bootstrap-server kafka:19092 --describe --group $(or $(GROUP),order-processors)
logs:
	$(COMPOSE) logs -f kafka
test:
	python -m unittest discover -s tests -v
down:
	$(COMPOSE) down
reset:
	$(COMPOSE) down -v
