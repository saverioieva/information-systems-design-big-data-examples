"""Declare one topic exchange per bounded context and per-consumer DLQs."""
import os
import time
import pika
from routing import TOPIC_EXCHANGES, QUEUE_BINDINGS, exchange_for_route

url = os.getenv("AMQP_URL", "amqp://student:student@rabbitmq:5672/%2F")
dlx = os.getenv("DLX", "saga.dlx")

while True:
    try:
        conn = pika.BlockingConnection(pika.URLParameters(url))
        break
    except (pika.exceptions.AMQPError, OSError):
        time.sleep(1)

try:
    ch = conn.channel()
    for exchange in TOPIC_EXCHANGES.values():
        ch.exchange_declare(exchange=exchange, exchange_type="topic", durable=True)
        print(f"[topology] topic_exchange={exchange}", flush=True)
    ch.exchange_declare(exchange=dlx, exchange_type="direct", durable=True)
    for queue, keys in QUEUE_BINDINGS.items():
        ch.queue_declare(queue=f"{queue}.dlq", durable=True)
        ch.queue_bind(exchange=dlx, queue=f"{queue}.dlq", routing_key=queue)
        ch.queue_declare(
            queue=queue, durable=True,
            arguments={"x-dead-letter-exchange": dlx, "x-dead-letter-routing-key": queue}
        )
        for key in keys:
            ch.queue_bind(exchange=exchange_for_route(key), queue=queue, routing_key=key)
        print(f"[topology] queue={queue} routes={keys} dead_letter_queue={queue}.dlq", flush=True)
finally:
    conn.close()
