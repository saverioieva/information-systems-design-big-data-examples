.PHONY: up down checkout-grpc checkout-rest inventory-rest compare unary server-stream client-stream bidi sniff generate-grpc-skeleton clean-generated logs test

up:
	docker compose up --build -d

down:
	docker compose down -v

checkout-grpc:
	curl -s -X POST http://localhost:8000/checkouts -H 'Content-Type: application/json' -d '{"sku":"pizza","quantity":2}'

checkout-rest:
	curl -s -X POST http://localhost:8001/checkouts -H 'Content-Type: application/json' -d '{"sku":"pizza","quantity":2}'

inventory-rest:
	curl -s -X POST http://localhost:8081/availability -H 'Content-Type: application/json' -d '{"sku":"pizza","quantity":2}'

compare:
	docker compose --profile tools run --rm grpc-client compare_unary.py

unary:
	docker compose --profile tools run --rm grpc-client unary.py

server-stream:
	docker compose --profile tools run --rm grpc-client server_streaming.py

client-stream:
	docker compose --profile tools run --rm grpc-client client_streaming.py

bidi:
	docker compose --profile tools run --rm grpc-client bidirectional.py

sniff:
	docker compose --profile tools run --rm grpc-sniffer

generate-grpc-skeleton:
	docker compose --profile codegen run --rm grpc-codegen

clean-generated:
	rm -rf generated

logs:
	docker compose logs -f

test:
	docker compose --profile tools run --rm test-runner
