"""RabbitMQ inbound: only ack after local transaction commits."""
import json
import time
import pika
from app.adapters.outbound.rabbitmq_transport import connect

def consume(role,use_cases):
    while True:
        try:
            conn=connect();ch=conn.channel()
            queue='saga.orchestrator' if role=='orchestrator' else f'saga.{role}'
            ch.basic_qos(prefetch_count=1)
            def on_message(channel,method,props,body):
                try:
                    use_cases.handle_message(json.loads(body))
                    channel.basic_ack(delivery_tag=method.delivery_tag)
                except Exception as exc:
                    print(f'[{role}] handler failed: {exc}',flush=True)
                    channel.basic_nack(delivery_tag=method.delivery_tag,requeue=False)
            ch.basic_consume(queue=queue,on_message_callback=on_message)
            ch.start_consuming()
        except (pika.exceptions.AMQPError,OSError):time.sleep(1)
