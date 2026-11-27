.PHONY: adminer up down reset logs test demo-happy demo-compensation demo-recovery demo-comparison demo-outage demo-catchup rebuild-projection inspect inspect-order inspect-accounting inspect-kitchen inspect-saga inspect-query kafka-info kafka-groups kafka-ui

up:
	docker compose up -d --build --wait order accounting kitchen orchestrator history stream-bridge kafka-ui

adminer:
	docker compose up -d adminer
	@echo "Adminer: http://localhost:8184 (PostgreSQL: server order-db, accounting-db, kitchen-db, or saga-db; database events; user/password demo)"

down:
	docker compose down

reset:
	docker compose down -v

logs:
	docker compose logs -f order accounting kitchen orchestrator history stream-bridge

test:
	docker compose run --rm --build --no-deps unit-tests

demo-happy:
	docker compose run --rm --no-deps --build demo --scenario happy

demo-compensation:
	docker compose run --rm --no-deps --build demo --scenario compensation

demo-recovery:
	@set -e; trap 'docker compose start accounting >/dev/null' EXIT; \
	 docker compose stop accounting; \
	 docker compose run --rm --no-deps --build demo --scenario create-only; \
	 docker compose run --rm --no-deps demo --scenario wait-started; \
	 docker compose restart orchestrator; \
	 docker compose start accounting; \
	 docker compose run --rm --no-deps demo --scenario show-last

inspect:
	@for service in order accounting kitchen orchestrator; do docker compose exec -T $$service python -c 'from lab.storage import EventStore; print(EventStore().stats())'; done

inspect-order:
	docker compose exec -T order-db psql -U demo -d events -c "SELECT aggregate_id,version,event_type,payload FROM events ORDER BY occurred_at,version LIMIT 30"

inspect-accounting:
	docker compose exec -T accounting-db psql -U demo -d events -c "SELECT aggregate_id,version,event_type,payload FROM events ORDER BY occurred_at,version LIMIT 30"

inspect-kitchen:
	docker compose exec -T kitchen-db psql -U demo -d events -c "SELECT aggregate_id,version,event_type,payload FROM events ORDER BY occurred_at,version LIMIT 30"

inspect-saga:
	docker compose exec -T saga-db psql -U demo -d events -c "SELECT aggregate_id,version,event_type,payload FROM events ORDER BY occurred_at,version LIMIT 40"

# Both strategies query the SAME order through the SAME external History API.
demo-comparison:
	docker compose run --rm --no-deps --entrypoint python demo -m scripts.compare --scenario compare

demo-outage:
	docker compose run --rm --no-deps --entrypoint python demo -m scripts.compare --scenario compare
	@trap 'docker compose start kitchen >/dev/null' EXIT; \
	 docker compose stop kitchen; \
	 docker compose run --rm --no-deps --entrypoint python demo -m scripts.compare --scenario compare-last

# Kafka retains integration events while the History consumer is offline.
demo-catchup:
	docker compose stop history
	@trap 'docker compose start history >/dev/null' EXIT; \
	 docker compose run --rm --no-deps demo --scenario create-only; \
	 docker compose start history; \
	 docker compose run --rm --no-deps --entrypoint python demo -m scripts.compare --scenario compare-last

# Stop the consumer before resetting its committed Kafka offsets. Then rebuild
# the MongoDB projection from the topic's EARLIEST RETAINED records.
# Run demo-comparison first to create and consume sample records.
rebuild-projection:
	@set -e; trap 'docker compose start history >/dev/null' EXIT; \
	 docker compose stop history; \
	 docker compose run --rm --no-deps --entrypoint python history -m scripts.reset_history; \
	 docker compose exec -T kafka /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server kafka:19092 --group order-history-view --topic orders.integration --reset-offsets --to-earliest --execute; \
	 docker compose start history; \
	 trap - EXIT; \
	 docker compose run --rm --no-deps --entrypoint python demo -m scripts.compare --scenario compare-last

inspect-query:
	docker compose exec -T history-db mongosh --quiet order_history --eval 'db.order_history.find({}, {_id:1, order_status:1, payment_status:1, kitchen_status:1, source_versions:1, timeline:1}).limit(10).forEach(printjson)'

kafka-info:
	docker compose exec -T kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:19092 --describe --topic orders.integration

kafka-groups:
	docker compose exec -T kafka /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server kafka:19092 --describe --group order-history-view

kafka-ui:
	@echo "Kafka UI: http://localhost:8087 (topic orders.integration, group order-history-view)"
