"""Outbound adapter: persistent delivery and RabbitMQ publisher confirms."""
import json
import os
import pika
from app.messaging_constants import EXCHANGE, ROUTING_KEY


class RabbitMQPublisher:
    def __init__(self):
        self.connection = pika.BlockingConnection(
            pika.URLParameters(os.getenv('AMQP_URL', 'amqp://student:student@rabbitmq:5672/%2F'))
        )
        self.channel = self.connection.channel()
        self.channel.exchange_declare(exchange=EXCHANGE, exchange_type='topic', durable=True)
        self.channel.confirm_delivery()

    def publish(self, event):
        acknowledged = self.channel.basic_publish(
            exchange=EXCHANGE, routing_key=ROUTING_KEY,
            body=json.dumps(event).encode('utf-8'), mandatory=True,
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type='application/json',
                message_id=event['eventId'], type=event['type'],
            ),
        )
        if acknowledged is False:
            raise RuntimeError('RabbitMQ did not confirm delivery')
        print(f"[relay] published eventId={event['eventId']} (broker confirmed)", flush=True)

    def close(self):
        if self.connection.is_open:
            self.connection.close()
