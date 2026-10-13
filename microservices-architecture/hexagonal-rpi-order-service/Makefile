.PHONY: generate-server-skeleton clean-generated

generate-server-skeleton:
	docker compose --profile codegen run --rm openapi-server-generator

clean-generated:
	rm -rf generated
