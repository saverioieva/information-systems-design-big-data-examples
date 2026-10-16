import os

from demos.common import connection, decode


EXCHANGE = "orders.partitioned"
ORDER_KEY = os.environ["ORDER_KEY"]
QUEUE = f"orders.partition.{ORDER_KEY.lower()}"
ROUTING_KEY = f"order.{ORDER_KEY}"


def main() -> None:
    conn = connection()
    channel = conn.channel()
    channel.exchange_declare(exchange=EXCHANGE, exchange_type="direct", durable=True)
    channel.queue_declare(queue=QUEUE, durable=True)
    channel.queue_bind(exchange=EXCHANGE, queue=QUEUE, routing_key=ROUTING_KEY)
    channel.basic_qos(prefetch_count=1)

    def handle(ch, method, properties, body: bytes) -> None:
        payload = decode(body)
        print(f"Order {ORDER_KEY}: sequence={payload['sequence']} event={payload['event']}", flush=True)
        ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(queue=QUEUE, on_message_callback=handle, auto_ack=False)
    print(f"Order {ORDER_KEY}: {ROUTING_KEY} -> {QUEUE}", flush=True)
    channel.start_consuming()


if __name__ == "__main__":
    main()
