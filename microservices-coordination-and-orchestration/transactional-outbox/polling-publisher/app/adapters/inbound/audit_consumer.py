"""RabbitMQ inbound adapter: ack only after idempotent storage commit."""
import json
import os
import time
import pika
from app.application.use_cases import AuditHandler
from app.adapters.outbound.postgres_audit_repository import PostgresAuditRepository
from app.adapters.outbound.rabbitmq_publisher import EXCHANGE

def run():
    repo = PostgresAuditRepository(); repo.initialize()
    handler = AuditHandler(repo)
    while True:
        try:
            connection = pika.BlockingConnection(pika.URLParameters(os.getenv('AMQP_URL','amqp://student:student@rabbitmq:5672/%2F')))
            channel = connection.channel()
            channel.exchange_declare(exchange=EXCHANGE, exchange_type='topic',durable=True)
            channel.queue_declare(queue='outbox.audit',durable=True)
            channel.queue_bind(exchange=EXCHANGE,queue='outbox.audit',routing_key='order.created')
            channel.basic_qos(prefetch_count=1)
            def on_message(ch,method,props,body):
                try:
                    handler.handle(json.loads(body))
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                except Exception:
                    ch.basic_nack(delivery_tag=method.delivery_tag,requeue=True)
                    raise
            channel.basic_consume(queue='outbox.audit',on_message_callback=on_message)
            channel.start_consuming()
        except (pika.exceptions.AMQPError,OSError): time.sleep(2)


if __name__ == "__main__":
    run()
