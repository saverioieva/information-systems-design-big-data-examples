"""Inbound RabbitMQ adapter; domain transition in application layer."""
import threading
from saga_common import publish_outbox_forever,run_consumer,flow
from saga_common.routing import QUEUE_BINDINGS
from application.use_cases import KitchenUseCases
from adapters.outbound.postgres_repository import PostgresKitchenRepository

repo=PostgresKitchenRepository();repo.initialize()
service=KitchenUseCases(repo)


def consume():
    def handler(event, properties, route):
        service.handle(event, properties, route)
    run_consumer("kitchen_service", "kitchen.q", QUEUE_BINDINGS["kitchen.q"], handler)


if __name__ == '__main__':
    threading.Thread(target=publish_outbox_forever, daemon=True).start()
    consume()
