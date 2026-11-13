"""Kafka -> RabbitMQ integration bridge; commit offsets only AFTER broker confirmation."""
import os
import time
from confluent_kafka import Consumer, TopicPartition, KafkaException

from bridge.application.forward import forward
from bridge.adapters.rabbitmq_transport import RabbitPublisher


def main():
    consumer = Consumer({
        'bootstrap.servers': os.getenv('KAFKA_BOOTSTRAP', 'kafka:19092'),
        'group.id': os.getenv('KAFKA_GROUP', 'orders-to-rabbit-bridge'),
        'auto.offset.reset': 'earliest',
        'enable.auto.commit': False,
    })
    consumer.subscribe([os.getenv('KAFKA_TOPIC', 'orders.integration')])
    publisher = None
    print('[bridge] subscribed to Kafka integration events', flush=True)
    try:
        while True:
            msg = consumer.poll(1)
            if msg is None:
                if publisher is not None:
                    try:
                        publisher.connection.process_data_events(time_limit=0)
                    except Exception:
                        try:
                            publisher.close()
                        except Exception:
                            pass
                        publisher = None
                continue
            if msg.error():
                raise KafkaException(msg.error())
            try:
                if publisher is None:
                    publisher = RabbitPublisher()
                event = forward(msg.value(), publisher)
                # At least once bridge delivery: publish + confirm, THEN commit offset.
                # A crash between these steps can republish the same event.
                consumer.commit(message=msg, asynchronous=False)
                print(f'[bridge] committed Kafka offset topic={msg.topic()} p={msg.partition()} '
                      f'offset={msg.offset()} eventId={event.event_id}', flush=True)
            except Exception as exc:
                print(f'[bridge] retrying same Kafka record after error: {exc}', flush=True)
                try:
                    if publisher is not None:
                        publisher.close()
                except Exception:
                    pass
                publisher = None
                consumer.seek(TopicPartition(msg.topic(), msg.partition(), msg.offset()))
                time.sleep(3)
    except KeyboardInterrupt:
        pass
    finally:
        if publisher is not None:
            publisher.close()
        consumer.close()


if __name__ == '__main__':
    main()
