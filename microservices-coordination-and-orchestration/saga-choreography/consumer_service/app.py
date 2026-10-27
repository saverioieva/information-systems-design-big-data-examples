"""RabbitMQ inbound adapter + composition root."""
import threading
from saga_common import publish_outbox_forever,run_consumer,flow
from application.use_cases import ConsumerUseCases
from adapters.outbound.postgres_repository import PostgresConsumerRepository

repo=PostgresConsumerRepository();repo.initialize()
service=ConsumerUseCases(repo)


def consume():
    def handler(event, properties, route):
        service.handle(event, properties)
    run_consumer("consumer_service", "consumer.q", ['order.created'], handler)


if __name__ == '__main__':
    threading.Thread(target=publish_outbox_forever, daemon=True).start()
    consume()
