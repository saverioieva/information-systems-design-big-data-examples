.PHONY: up down logs demo test inspect reset
up:
	docker compose up -d --build db app

down:
	docker compose down

logs:
	docker compose logs -f app

demo:
	python3 scripts/demo.py

test:
	docker compose build app
	docker compose run --rm --no-deps -e DATABASE_URL=sqlite+pysqlite:///:memory: app python -m pytest -q tests

inspect:
	docker compose exec -T db psql -U ftgo -d ftgo -c 'SELECT id,state,version FROM orders ORDER BY id LIMIT 10;'

reset:
	docker compose down -v
