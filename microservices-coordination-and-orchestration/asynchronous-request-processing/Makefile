COMPOSE=docker compose
ORDER_ID ?= ORD-1001

.PHONY: help up down reset logs ps create status invalid-consumer invalid-item queues management test

help:
	@echo 'Asynchronous Request Processing -- RabbitMQ + Flask'
	@echo '  make up                  Start RabbitMQ and all four Python processes'
	@echo '  make logs                Follow logs of the three services and result listener'
	@echo '  make create              Create PENDING order (ORDER_ID=ORD-1001)'
	@echo '  make status              Inspect ORDER_ID status'
	@echo '  make invalid-consumer    Demonstrate rejection when consumer_id=blocked'
	@echo '  make invalid-item        Demonstrate rejection when item=unavailable'
	@echo '  make queues              List RabbitMQ queues'
	@echo '  make test                Run local tests in a transient container'
	@echo '  make down                Stop without removing data'
	@echo '  make reset               DESTRUCTIVE: delete all lab volumes'

up:
	$(COMPOSE) up -d --build

ps:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f order-api order-results consumer-service restaurant-service

create:
	curl -i -sS -X POST http://localhost:5001/orders -H 'Content-Type: application/json' -d '{"order_id":"$(ORDER_ID)","consumer_id":"CUST-1","item":"pizza"}'

status:
	curl -sS http://localhost:5001/orders/$(ORDER_ID); echo

invalid-consumer:
	curl -i -sS -X POST http://localhost:5001/orders -H 'Content-Type: application/json' -d '{"order_id":"ORD-BLOCKED","consumer_id":"blocked","item":"pizza"}'

invalid-item:
	curl -i -sS -X POST http://localhost:5001/orders -H 'Content-Type: application/json' -d '{"order_id":"ORD-NO-PIZZA","consumer_id":"CUST-1","item":"unavailable"}'

queues:
	$(COMPOSE) exec rabbitmq rabbitmqctl list_queues name messages consumers durable

management:
	@echo 'RabbitMQ Management: http://localhost:15672  (student / student)'

test:
	$(COMPOSE) run --rm --no-deps order-api python -m unittest discover -s tests -v

down:
	$(COMPOSE) down

reset:
	$(COMPOSE) down -v --remove-orphans
