COMPOSE=docker compose
.PHONY: up logs flow approve decline invalid poison dlq down reset test
up:
	$(COMPOSE) up -d --build
logs:
	$(COMPOSE) logs -f order_service consumer_service kitchen_service accounting_service
approve:
	curl -fsS -X POST http://localhost:8002/orders -H 'Content-Type: application/json' -d '{"customerId":"CUST_1","amount":42.0}'
decline:
	curl -fsS -X POST http://localhost:8002/orders -H 'Content-Type: application/json' -d '{"customerId":"CUST_1","amount":150.0}'
invalid:
	curl -fsS -X POST http://localhost:8002/orders -H 'Content-Type: application/json' -d '{"customerId":"CUST_INVALID","amount":42.0}'
test:
	python -m compileall -q order_service consumer_service kitchen_service accounting_service libs topology.py
	python -m unittest discover -s tests -v
down:
	$(COMPOSE) down
reset:
	$(COMPOSE) down -v

flow:
	$(COMPOSE) logs -f order_service consumer_service kitchen_service accounting_service | grep --line-buffered '\[flow\]'
poison:
	curl -fsS -u student:student -H 'Content-Type: application/json' -X POST http://localhost:15674/api/exchanges/%2F/saga/publish -d '{"properties":{"delivery_mode":2},"routing_key":"consumer.verified","payload":"{\"orderId\":\"DLQ-DEMO\"}","payload_encoding":"string"}'
	@echo 'Inspect accounting.q.dlq in RabbitMQ Management (Queues and Streams).'
dlq:
	$(COMPOSE) exec -T rabbitmq rabbitmqctl list_queues name messages_ready | grep -E '(name|\.dlq)'
