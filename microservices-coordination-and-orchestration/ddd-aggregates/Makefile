COMPOSE=docker compose
.PHONY: up down reset logs test
up:
	$(COMPOSE) up -d --build
logs:
	$(COMPOSE) logs -f app
test:
	python -m unittest discover -s tests -v
down:
	$(COMPOSE) down
reset:
	$(COMPOSE) down -v
