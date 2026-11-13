COMPOSE=docker compose
.PHONY: up down reset logs create approve events db test test-local
up:
	$(COMPOSE) up -d --build
logs:
	$(COMPOSE) logs -f app
create:
	curl -fsS -X POST http://localhost:8003/orders -H 'Content-Type: application/json' -d '{"consumer_id":"CUST_1","restaurant_id":"REST_1","line_items":[{"menu_item_id":"PIZZA","name":"Pizza","price":10.0,"quantity":2}]}'
approve:
	@test -n "$(ORDER_ID)" || (echo 'Usage: make approve ORDER_ID=<id> [VERSION=1]'; exit 1)
	curl -fsS -X POST "http://localhost:8003/orders/$(ORDER_ID)/approve?expected_version=$(or $(VERSION),1)"
events:
	curl -fsS http://localhost:8003/lab/outbox
db:
	$(COMPOSE) exec -T db psql -U ftgo -d ftgo -c 'SELECT event_type, aggregate_id, created_at FROM integration_outbox ORDER BY created_at'
test:
	$(COMPOSE) build app
	$(COMPOSE) run --rm --no-deps -e DATABASE_URL=sqlite+pysqlite:///:memory: -v "$(CURDIR):/code" app python -m unittest discover -s tests -v
test-local:
	DATABASE_URL=sqlite+pysqlite:///:memory: python -m unittest discover -s tests -v
down:
	$(COMPOSE) down
reset:
	$(COMPOSE) down -v
