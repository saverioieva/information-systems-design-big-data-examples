COMPOSE=docker compose
LAB=$(COMPOSE) --profile tools run --rm lab

.PHONY: build up status management queues exchanges bindings \
        work-up work-demo work-stop \
        fanout-up fanout-demo fanout-stop \
        direct-up direct-demo direct-stop \
        topic-up topic-demo topic-stop \
        headers-up headers-demo headers-stop \
        rpc-up rpc-demo rpc-stop \
        duplicate-up duplicate-demo duplicate-stop redelivery-demo \
        ordering-up ordering-demo ordering-stop \
        test down reset

build:
	$(COMPOSE) --profile tools build lab

up:
	$(COMPOSE) up -d rabbitmq

status:
	$(COMPOSE) ps

management:
	@echo "RabbitMQ Management UI: http://localhost:15672"
	@echo "username: student"
	@echo "password: student"

queues:
	$(COMPOSE) exec rabbitmq rabbitmqctl -q --formatter=pretty_table list_queues name messages messages_ready messages_unacknowledged consumers durable

exchanges:
	$(COMPOSE) exec rabbitmq rabbitmqctl -q --formatter=pretty_table list_exchanges name type durable

bindings:
	$(COMPOSE) exec rabbitmq rabbitmqctl -q --formatter=pretty_table list_bindings source_name destination_name destination_kind routing_key

work-up:
	$(COMPOSE) --profile work up -d --build rabbitmq work-worker-a work-worker-b

work-demo: work-up
	$(LAB) python -m demos.work_queue.publisher --count 8
	@sleep 5
	$(COMPOSE) logs --tail=80 work-worker-a work-worker-b

work-stop:
	$(COMPOSE) stop work-worker-a work-worker-b

fanout-up:
	$(COMPOSE) --profile fanout up -d --build rabbitmq fanout-inventory fanout-notification

fanout-demo: fanout-up
	$(LAB) python -m demos.fanout.publisher --order-id order-123
	@sleep 1
	$(COMPOSE) logs --tail=30 fanout-inventory fanout-notification

fanout-stop:
	$(COMPOSE) stop fanout-inventory fanout-notification

# Direct exchange: audit receives both messages; failure-monitor receives only order.failed.
direct-up:
	$(COMPOSE) --profile direct up -d --build rabbitmq direct-all direct-failures

direct-demo: direct-up
	$(LAB) python -m demos.direct.publisher order.created --order-id order-201
	$(LAB) python -m demos.direct.publisher order.failed --order-id order-202
	@sleep 1
	$(COMPOSE) logs --tail=40 direct-all direct-failures

direct-stop:
	$(COMPOSE) stop direct-all direct-failures

# Topic exchange: order-history binds order.*; onboarding-flow binds order.created.
topic-up:
	$(COMPOSE) --profile topic up -d --build rabbitmq topic-all topic-created topic-any-depth topic-any-created

topic-demo: topic-up
	$(LAB) python -m demos.topic.publisher order.created --order-id order-301
	$(LAB) python -m demos.topic.publisher order.updated --order-id order-301
	$(LAB) python -m demos.topic.publisher order.failed --order-id order-302
	@sleep 1
	$(COMPOSE) logs --tail=70 topic-all topic-created topic-any-depth topic-any-created

topic-stop:
	$(COMPOSE) stop topic-all topic-created topic-any-depth topic-any-created

# Headers exchange: eu-order-handler requires region=eu AND type=order.
# payment-handler requires type=payment; extra message headers are allowed.
headers-up:
	$(COMPOSE) --profile headers up -d --build rabbitmq headers-eu-orders headers-payments

headers-demo: headers-up
	$(LAB) python -m demos.headers.publisher --type order --region eu
	$(LAB) python -m demos.headers.publisher --type order --region us
	$(LAB) python -m demos.headers.publisher --type payment --region eu
	@sleep 1
	$(COMPOSE) logs --tail=50 headers-eu-orders headers-payments

headers-stop:
	$(COMPOSE) stop headers-eu-orders headers-payments

rpc-up:
	$(COMPOSE) --profile rpc up -d --build rabbitmq rpc-server

rpc-demo: rpc-up
	$(LAB) python -m demos.request_reply.client --order-id order-401 --subtotal 25.50
	$(LAB) python -m demos.request_reply.client --order-id order-402 --subtotal 42.00
	$(COMPOSE) logs --tail=30 rpc-server

rpc-stop:
	$(COMPOSE) stop rpc-server

duplicate-up:
	$(COMPOSE) --profile reliability up -d --build rabbitmq idempotent-consumer

duplicate-demo: duplicate-up
	$(LAB) python -m demos.reliability.duplicate_publisher
	@sleep 1
	$(COMPOSE) logs --tail=40 idempotent-consumer

duplicate-stop:
	$(COMPOSE) stop idempotent-consumer

redelivery-demo:
	$(COMPOSE) up -d rabbitmq
	$(LAB) python -m demos.reliability.redelivery_publisher
	-$(LAB) python -m demos.reliability.redelivery_consumer --crash-before-ack
	@sleep 2
	$(LAB) python -m demos.reliability.redelivery_consumer

ordering-up:
	$(COMPOSE) --profile ordering up -d --build rabbitmq ordering-a ordering-b

ordering-demo: ordering-up
	$(LAB) python -m demos.ordering.publisher
	@sleep 1
	$(COMPOSE) logs --tail=50 ordering-a ordering-b

ordering-stop:
	$(COMPOSE) stop ordering-a ordering-b

test:
	$(COMPOSE) --profile tools build lab
	$(COMPOSE) --profile tools run --rm --no-deps lab python -m compileall -q demos

down:
	$(COMPOSE) --profile work --profile fanout --profile direct --profile topic --profile headers --profile rpc --profile reliability --profile ordering down --remove-orphans

reset:
	$(COMPOSE) --profile work --profile fanout --profile direct --profile topic --profile headers --profile rpc --profile reliability --profile ordering down -v --remove-orphans
