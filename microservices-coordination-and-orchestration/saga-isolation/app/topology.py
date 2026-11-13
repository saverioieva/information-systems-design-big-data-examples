"""Provision durable queues before services start.

Retry queues delay commands via TTL, then dead-letter back into the matching
primary command queue, using the same topic exchange.
"""
from app.adapters.outbound.rabbitmq_transport import connect, EXCHANGE


def provision():
    conn = connect()
    try:
        ch = conn.channel()
        ch.exchange_declare(exchange=EXCHANGE, exchange_type='topic', durable=True)
        for role, key in (('orchestrator', 'reply.orchestrator'),
                          ('consumer', 'command.consumer'),
                          ('kitchen', 'command.kitchen'),
                          ('accounting', 'command.accounting'),
                          ('order', 'command.order')):
            queue = f'saga.{role}'
            ch.queue_declare(queue=queue, durable=True)
            ch.queue_bind(exchange=EXCHANGE, queue=queue, routing_key=key)
            print(f'declared {queue} for {key}', flush=True)

        for role in ('kitchen', 'order'):
            queue = f'saga.retry.{role}'
            ch.queue_declare(queue=queue, durable=True, arguments={
                'x-message-ttl': 2000,
                'x-dead-letter-exchange': EXCHANGE,
                'x-dead-letter-routing-key': f'command.{role}',
            })
            ch.queue_bind(exchange=EXCHANGE, queue=queue, routing_key=f'retry.command.{role}')
            print(f'declared delayed retry queue {queue} (2s TTL)', flush=True)
    finally:
        conn.close()


if __name__ == '__main__':
    provision()
