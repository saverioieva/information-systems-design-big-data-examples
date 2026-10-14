.PHONY: up down run-v1.0.0 run-v1.1.0 run-v1.1.1 status client-v1 client-v2 client-media-v1 client-media-v2

up: run-v1.1.1

run-v1.0.0:
	ORDER_V1_SERVICE_VERSION=1.0.0 docker compose up -d --build --force-recreate

run-v1.1.0:
	ORDER_V1_SERVICE_VERSION=1.1.0 docker compose up -d --build --force-recreate

run-v1.1.1:
	ORDER_V1_SERVICE_VERSION=1.1.1 docker compose up -d --build --force-recreate

status:
	docker compose ps

client-v1:
	docker compose --profile tools run --rm client python client_v1.py --url http://api-gateway/v1/orders/123

client-v2:
	docker compose --profile tools run --rm client python client_v2.py --url http://api-gateway/v2/orders/123

client-media-v1:
	docker compose --profile tools run --rm client python client_media_type.py --version 1 --url http://api-gateway/orders/123

client-media-v2:
	docker compose --profile tools run --rm client python client_media_type.py --version 2 --url http://api-gateway/orders/123

down:
	docker compose down -v
