import os

from demos.common import connection, decode


EXCHANGE = "orders.topic"
QUEUE = os.environ["QUEUE_NAME"]
BINDING_KEY = os.environ["BINDING_KEY"]
CONSUMER = os.getenv("CONSUMER_NAME", QUEUE)


def main() -> None:
    conn = connection()
    channel = conn.channel()
    channel.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)
    channel.queue_declare(queue=QUEUE, durable=True)
    channel.queue_bind(exchange=EXCHANGE, queue=QUEUE, routing_key=BINDING_KEY)

    def handle(ch, method, properties, body: bytes) -> None:
        payload = decode(body)
        print(f"{CONSUMER}: matched {method.routing_key} order={payload['orderId']}", flush=True)
        ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(queue=QUEUE, on_message_callback=handle, auto_ack=False)
    print(f"{CONSUMER}: binding={BINDING_KEY}", flush=True)
    channel.start_consuming()


if __name__ == "__main__":
    main()
