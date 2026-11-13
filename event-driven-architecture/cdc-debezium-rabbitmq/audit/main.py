"""RabbitMQ subscriber: ACK after local Inbox commit; poison messages -> DLQ."""
import json
import sys
import time
import pika

from audit.inbox import AuditInbox
from bridge.adapters.rabbitmq_transport import connect, declare_topology, EXCHANGE, QUEUE


def observe():
    inbox = AuditInbox()
    while True:
        conn = None
        try:
            conn = connect()
            channel = conn.channel()
            declare_topology(channel)
            channel.basic_qos(prefetch_count=1)

            def callback(ch, method, properties, body):
                try:
                    record = json.loads(body)
                    is_new = inbox.record(record)
                    print(f'[audit] {"stored" if is_new else "duplicate"} '
                          f'{record["type"]} eventId={record["eventId"]}', flush=True)
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                except Exception as exc:
                    print(f'[audit] malformed event -> DLQ: {exc}', flush=True)
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            channel.basic_consume(queue=QUEUE, on_message_callback=callback, auto_ack=False)
            print('[audit] consuming audit.orders with persistent Inbox deduplication', flush=True)
            channel.start_consuming()
        except KeyboardInterrupt:
            break
        except Exception as exc:
            print(f'[audit] reconnecting after: {exc}', flush=True)
            time.sleep(3)
        finally:
            if conn is not None and conn.is_open:
                conn.close()


def poison():
    conn = connect()
    try:
        channel = conn.channel()
        declare_topology(channel)
        channel.basic_publish(exchange=EXCHANGE, routing_key='order.created',
                              body=b'{ intentionally invalid JSON',
                              properties=pika.BasicProperties(delivery_mode=2))
        print('[audit] intentionally malformed message published; see audit.orders.dlq')
    finally:
        conn.close()


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--list':
        for item in AuditInbox().list_records():
            print(json.dumps(item))
    elif len(sys.argv) > 1 and sys.argv[1] == '--poison':
        poison()
    else:
        observe()
