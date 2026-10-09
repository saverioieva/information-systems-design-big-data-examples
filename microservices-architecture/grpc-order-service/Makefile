.PHONY: generate up down unary server-stream client-stream bidi rest logs

generate:
	./scripts/generate_proto.sh

up:
	docker compose up --build -d

down:
	docker compose down -v

unary:
	docker compose --profile tools run --rm grpc-client unary.py

server-stream:
	docker compose --profile tools run --rm grpc-client server_streaming.py

client-stream:
	docker compose --profile tools run --rm grpc-client client_streaming.py

bidi:
	docker compose --profile tools run --rm grpc-client bidirectional.py

rest:
	python demo-clients/rest_client.py

logs:
	docker compose logs -f
