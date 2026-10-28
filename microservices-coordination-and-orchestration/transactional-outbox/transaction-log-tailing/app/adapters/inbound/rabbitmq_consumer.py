"""Inbound AMQP adapter: setup, consume, and acknowledge after commit."""
import os
import time
import pika
from app.application.use_cases import AuditDeliveryHandler
from app.adapters.outbound.postgres_audit_repository import PostgresAuditRepository
from app.messaging_constants import EXCHANGE, QUEUE, ROUTING_KEY

AMQP_URL = os.getenv("AMQP_URL", "amqp://student:student@rabbitmq:5672/%2F")

def connect():
    while True:
        try:
            return pika.BlockingConnection(pika.URLParameters(AMQP_URL))
        except (pika.exceptions.AMQPConnectionError, OSError) as exc:
            print(f"[amqp] waiting: {exc}", flush=True)
            time.sleep(2)

def declare(channel):
    channel.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)
    channel.queue_declare(queue=QUEUE, durable=True)
    channel.queue_bind(queue=QUEUE, exchange=EXCHANGE, routing_key=ROUTING_KEY)

def topology():
    conn = connect()
    try:
        declare(conn.channel())
        print("[setup] durable exchange, queue and binding declared", flush=True)
    finally:
        conn.close()


def consumer():
    service = AuditDeliveryHandler(PostgresAuditRepository())
    while True:
        conn = connect()
        try:
            channel = conn.channel()
            declare(channel)
            channel.basic_qos(prefetch_count=1)

            def on_message(ch, method, props, body):
                try:
                    message = service.handle_delivery(body)
                    print(f"[consumer] OrderCreated received eventId={message['eventId']}", flush=True)
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                except Exception as exc:
                    # Teaching demo: reject malformed messages instead of infinite hot-loop requeues.
                    print(f"[consumer] rejected message: {exc}", flush=True)
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            channel.basic_consume(queue=QUEUE, on_message_callback=on_message)
            print("[consumer] waiting for outbox events", flush=True)
            channel.start_consuming()
        except (pika.exceptions.AMQPError, OSError) as exc:
            print(f"[consumer] reconnecting: {exc}", flush=True)
            time.sleep(2)
        finally:
            if conn.is_open:
                conn.close()

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2 or sys.argv[1] not in {"topology", "consumer"}:
        raise SystemExit("Usage: python -m app.messaging topology|consumer")
    globals()[sys.argv[1]]()
