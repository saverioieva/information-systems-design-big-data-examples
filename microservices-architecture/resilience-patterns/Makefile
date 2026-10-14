.PHONY: up down logs test bulkhead-demo

up:
	docker compose up --build -d

down:
	docker compose down -v

logs:
	docker compose logs -f gateway

test:
	docker compose run --rm gateway python -m unittest discover -s /app/tests -v

bulkhead-demo:
	docker compose --profile tools run --rm bulkhead-demo
