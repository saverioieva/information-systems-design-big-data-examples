COMPOSE=docker compose
KAFKA=$(COMPOSE) exec -T kafka /opt/kafka/bin
.PHONY: up down reset logs topics partitions produce consume replay worker groups test
up:
	$(COMPOSE) up -d kafka
	$(COMPOSE) run --rm topics
	$(COMPOSE) build client
status:
	$(COMPOSE) ps
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
	$(COMPOSE) run --rm client python -m app.main consume --group shared-workers --limit 0 --idle 0
groups:
	$(KAFKA)/kafka-consumer-groups.sh --bootstrap-server kafka:19092 --list
logs:
	$(COMPOSE) logs -f kafka
test:
	python -m unittest discover -s tests -v
down:
	$(COMPOSE) down
reset:
	$(COMPOSE) down -v
