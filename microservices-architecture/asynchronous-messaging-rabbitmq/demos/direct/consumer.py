import os

from demos.common import connection, decode


EXCHANGE = "orders.direct"
QUEUE = os.environ["QUEUE_NAME"]
BINDING_KEYS = [key.strip() for key in os.environ["BINDING_KEYS"].split(",") if key.strip()]
CONSUMER = os.getenv("CONSUMER_NAME", QUEUE)


def main() -> None:
    conn = connection()
    channel = conn.channel()
    channel.exchange_declare(exchange=EXCHANGE, exchange_type="direct", durable=True)
    channel.queue_declare(queue=QUEUE, durable=True)
    for key in BINDING_KEYS:
        channel.queue_bind(exchange=EXCHANGE, queue=QUEUE, routing_key=key)

    def handle(ch, method, properties, body: bytes) -> None:
        payload = decode(body)
        print(f"{CONSUMER}: key={method.routing_key} order={payload['orderId']}", flush=True)
        ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(queue=QUEUE, on_message_callback=handle, auto_ack=False)
    print(f"{CONSUMER}: bindings={BINDING_KEYS}", flush=True)
    channel.start_consuming()


if __name__ == "__main__":
    main()
