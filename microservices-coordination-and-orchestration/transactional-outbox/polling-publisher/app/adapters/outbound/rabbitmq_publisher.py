"""AMQP-specific implementation of MessagePublisher."""
import json
import os
import time
import pika

EXCHANGE = 'outbox.events'

class RabbitPublisher:
    def __init__(self):
        self._connection = None
        self._channel = None
    def _ready(self):
        if self._connection and self._connection.is_open and self._channel and self._channel.is_open:
            return self._channel
        url = os.getenv('AMQP_URL','amqp://student:student@rabbitmq:5672/%2F')
        self._connection = pika.BlockingConnection(pika.URLParameters(url))
        self._channel = self._connection.channel()
        self._channel.exchange_declare(exchange=EXCHANGE,exchange_type='topic',durable=True)
        self._channel.confirm_delivery()
        return self._channel
    def publish(self, routing_key: str, message: dict, event_id: str) -> None:
        self._ready().basic_publish(exchange=EXCHANGE,routing_key=routing_key,
            body=json.dumps(message).encode(), mandatory=True,
            properties=pika.BasicProperties(content_type='application/json',delivery_mode=2,message_id=event_id))
    def close(self):
        if self._connection and self._connection.is_open: self._connection.close()
