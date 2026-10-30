"""RabbitMQ inbound adapter + composition root."""
import threading
from saga_common import publish_outbox_forever,run_consumer,flow
from saga_common.routing import QUEUE_BINDINGS
from application.use_cases import AccountingUseCases
from adapters.outbound.postgres_repository import PostgresAccountingRepository
repo=PostgresAccountingRepository();repo.initialize()
service=AccountingUseCases(repo)


def consume():
    def handler(event, properties, route):
        service.handle(event, properties, route)
    run_consumer("accounting_service", "accounting.q", QUEUE_BINDINGS["accounting.q"], handler)


if __name__ == '__main__':
    threading.Thread(target=publish_outbox_forever, daemon=True).start()
    consume()
