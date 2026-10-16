import os

from demos.common import connection, decode


EXCHANGE = "orders.fanout"
QUEUE = os.environ["QUEUE_NAME"]
CONSUMER = os.getenv("CONSUMER_NAME", QUEUE)


def main() -> None:
    conn = connection()
    channel = conn.channel()
    channel.exchange_declare(exchange=EXCHANGE, exchange_type="fanout", durable=True)
    channel.queue_declare(queue=QUEUE, durable=True)
    channel.queue_bind(exchange=EXCHANGE, queue=QUEUE)

    def handle(ch, method, properties, body: bytes) -> None:
        payload = decode(body)
        print(f"{CONSUMER}: received {payload['type']} order={payload['orderId']}", flush=True)
        ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(queue=QUEUE, on_message_callback=handle, auto_ack=False)
    print(f"{CONSUMER}: queue={QUEUE} bound to fanout exchange", flush=True)
    channel.start_consuming()


if __name__ == "__main__":
    main()
