.PHONY: generate up down rest unary server-stream client-stream bidi sniff logs test

generate:
	./scripts/generate_proto.sh

up:
	docker compose up --build -d

down:
	docker compose down -v

rest:
	python demo-clients/rest_client.py

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

logs:
	docker compose logs -f

test:
	pytest -q
