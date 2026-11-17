"""Run the same redelivery scenario against PostgreSQL or MongoDB."""
import argparse
import json
from uuid import uuid4
from app.domain.idempotency import IncomingMessage, rebuild
from app.application.idempotency_service import IdempotentEventConsumer


def run(backend):
    backend.initialize()
    consumer = IdempotentEventConsumer(backend)
    order_id = 'class-' + uuid4().hex[:10]
    created = IncomingMessage(str(uuid4()), order_id, 'OrderCreated')
    approved = IncomingMessage(str(uuid4()), order_id, 'OrderApproved')
    for title, message in [
        ('1. First delivery', created),
        ('2. DUPLICATE delivery with exactly the same message ID', created),
        ('3. New message ID', approved),
        ('4. DUPLICATE approval', approved),
    ]:
        outcome = consumer.handle(message)
        accepted = outcome["accepted"]
        events = backend.events(order_id)
        print(f'\n{title}\n  messageId={message.message_id}\n  result={"appended" if accepted else "duplicate ignored"}'
              f'\n  eventCount={len(events)}  replayState={rebuild(events)}', flush=True)
    events = backend.events(order_id)
    assert len(events) == 2
    assert rebuild(events) == 'APPROVED'
    print('\nEvent stream (same semantics on either backend):')
    print(json.dumps(events, indent=2))
    print('\nPASS: 4 deliveries -> exactly 2 appended events.')
    if hasattr(backend, 'close'):
        backend.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--backend', choices=('postgres', 'mongo'), required=True)
    args = parser.parse_args()
    if args.backend == 'postgres':
        from app.adapters.outbound.postgres_inbox import PostgresInboxEventStore
        run(PostgresInboxEventStore())
    else:
        from app.adapters.outbound.mongo_inbox import MongoInboxEventStore
        run(MongoInboxEventStore())
