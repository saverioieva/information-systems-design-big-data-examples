"""Inbound RabbitMQ adapter: acknowledge only after durable local commit."""
import json
import time
import pika

from app.adapters.outbound.rabbitmq_transport import connect


def consume(role, handler):
    delay = 1
    while True:
        try:
            conn = connect()
            channel = conn.channel()
            queue = f'saga.{role}'
            channel.basic_qos(prefetch_count=1)
            delay = 1

            def on_message(ch, delivery, properties, body):
                try:
                    handler.handle_message(json.loads(body))
                    ch.basic_ack(delivery_tag=delivery.delivery_tag)
                except Exception as exc:
                    print(f'[flow] role={role} handler rejected message: {exc}', flush=True)
                    # The demo's deterministic retriable failures are managed by
                    # the application through the durable outbox + TTL retry queue.
                    # Unexpected errors are NOT automatically retried indefinitely.
                    ch.basic_nack(delivery_tag=delivery.delivery_tag, requeue=False)

            channel.basic_consume(queue=queue, on_message_callback=on_message)
            channel.start_consuming()
        except (pika.exceptions.AMQPError, OSError) as exc:
            print(f'[flow] role={role} RabbitMQ reconnect in {delay}s: {exc}', flush=True)
            time.sleep(delay)
            delay = min(delay * 2, 10)
