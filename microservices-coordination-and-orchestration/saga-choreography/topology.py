
"""Provision durable saga queues and one DLQ per consumer before services start."""
import os
import time
import pika

url = os.getenv("AMQP_URL", "amqp://student:student@rabbitmq:5672/%2F")
exchange = os.getenv("EXCHANGE", "saga")
dlx = os.getenv("DLX", "saga.dlx")

while True:
    try:
        conn = pika.BlockingConnection(pika.URLParameters(url))
        break
    except (pika.exceptions.AMQPError, OSError):
        time.sleep(1)

try:
    ch = conn.channel()
    ch.exchange_declare(exchange=exchange, exchange_type="topic", durable=True)
    ch.exchange_declare(exchange=dlx, exchange_type="direct", durable=True)
    routes = {
        "consumer.q": ["order.created"],
        "kitchen.q": ["order.created", "accounting.creditCardAuthorized", "accounting.creditCardAuthorizationFailed"],
        "accounting.q": ["order.created", "consumer.verified", "consumer.verificationFailed", "kitchen.ticketCreated"],
        "order.q": ["accounting.creditCardAuthorized", "accounting.creditCardAuthorizationFailed"],
        "audit.q": ["order.approved", "order.rejected", "kitchen.ticketRejected"],
    }
    for queue, keys in routes.items():
        ch.queue_declare(queue=f"{queue}.dlq", durable=True)
        ch.queue_bind(exchange=dlx, queue=f"{queue}.dlq", routing_key=queue)
        ch.queue_declare(
            queue=queue, durable=True,
            arguments={"x-dead-letter-exchange": dlx, "x-dead-letter-routing-key": queue}
        )
        for key in keys:
            ch.queue_bind(exchange=exchange, queue=queue, routing_key=key)
        print(f"[topology] queue={queue} routes={keys} dead_letter_queue={queue}.dlq", flush=True)
finally:
    conn.close()
