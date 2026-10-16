.PHONY: generate-server-skeleton run-generated-server stop-generated-server generated-demo clean-generated

generate-server-skeleton:
	docker compose --profile codegen run --rm openapi-server-generator

run-generated-server: generate-server-skeleton
	@docker compose stop order-fastapi order-flask >/dev/null 2>&1 || true
	docker compose --profile generated up --build -d postgres db-init order-generated
	@echo "Generated server: http://localhost:8000"

stop-generated-server:
	docker compose --profile generated stop order-generated

generated-demo: run-generated-server
	docker compose --profile generated run --rm generated-client

clean-generated:
	rm -rf generated
