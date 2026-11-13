"""RabbitMQ topology and publisher confirms. Messages can be redelivered on recovery."""
import os
import pika

EXCHANGE = 'orders.events'
QUEUE = 'audit.orders'
DLX = 'orders.dlx'
DLQ = 'audit.orders.dlq'


def connect():
    url = os.getenv('RABBITMQ_URL', 'amqp://student:student@rabbitmq:5672/')
    return pika.BlockingConnection(pika.URLParameters(url))


def declare_topology(channel):
    channel.exchange_declare(exchange=EXCHANGE, exchange_type='topic', durable=True)
    channel.exchange_declare(exchange=DLX, exchange_type='direct', durable=True)
    channel.queue_declare(queue=QUEUE, durable=True,
                          arguments={'x-dead-letter-exchange': DLX,
                                     'x-dead-letter-routing-key': 'audit.dead'})
    channel.queue_bind(queue=QUEUE, exchange=EXCHANGE, routing_key='order.*')
    channel.queue_declare(queue=DLQ, durable=True)
    channel.queue_bind(queue=DLQ, exchange=DLX, routing_key='audit.dead')


class RabbitPublisher:
    def __init__(self):
        self.connection = connect()
        self.channel = self.connection.channel()
        declare_topology(self.channel)
        self.channel.confirm_delivery()

    def publish(self, record):
        # mandatory=True + confirms mean the bridge does not commit the Kafka
        # offset for a rejected/unroutable RabbitMQ message.
        self.channel.basic_publish(
            exchange=EXCHANGE, routing_key=record.routing_key, body=record.payload,
            mandatory=True,
            properties=pika.BasicProperties(delivery_mode=2, content_type='application/json',
                                             message_id=record.event_id,
                                             headers={'eventId': record.event_id}),
        )
        print(f'[bridge] confirmed RabbitMQ publish {record.routing_key} eventId={record.event_id}', flush=True)

    def close(self):
        if self.connection.is_open:
            self.connection.close()
