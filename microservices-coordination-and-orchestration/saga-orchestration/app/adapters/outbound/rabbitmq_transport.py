"""AMQP outbound adapter: persistent messages and publisher confirms."""
import os
import time
import pika
EXCHANGE='saga.transport'

def connect():
    url=os.getenv('AMQP_URL','amqp://student:student@rabbitmq:5672/%2F')
    while True:
        try:return pika.BlockingConnection(pika.URLParameters(url))
        except (pika.exceptions.AMQPConnectionError,OSError):time.sleep(1)

class RabbitPublisher:
    def __init__(self,connection):
        self.channel=connection.channel()
        self.channel.confirm_delivery()
    def publish(self,record):
        self.channel.basic_publish(exchange=EXCHANGE,routing_key=record['routing_key'],
             body=record['payload'].encode(),mandatory=True,
             properties=pika.BasicProperties(delivery_mode=2,content_type='application/json',message_id=record['event_id']))
