.PHONY: test test-local
# Container-backed DDD tests also install their SQL dependencies.
test:
	$(MAKE) -C ddd-aggregates test
	$(MAKE) -C kafka-fundamentals test
	$(MAKE) -C cdc-debezium-rabbitmq test
# For development environments with SQLAlchemy installed locally.
test-local:
	$(MAKE) -C ddd-aggregates test-local
	$(MAKE) -C kafka-fundamentals test
	$(MAKE) -C cdc-debezium-rabbitmq test
