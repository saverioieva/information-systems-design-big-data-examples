import json
import os

from demos.common import connection, decode


EXCHANGE = "orders.headers"
QUEUE = os.environ["QUEUE_NAME"]
BINDING_HEADERS = json.loads(os.environ["BINDING_HEADERS"])
CONSUMER = os.getenv("CONSUMER_NAME", QUEUE)


def main() -> None:
    conn = connection()
    channel = conn.channel()
    channel.exchange_declare(exchange=EXCHANGE, exchange_type="headers", durable=True)
    channel.queue_declare(queue=QUEUE, durable=True)
    arguments = {"x-match": "all", **BINDING_HEADERS}
    channel.queue_bind(exchange=EXCHANGE, queue=QUEUE, arguments=arguments)

    def handle(ch, method, properties, body: bytes) -> None:
        payload = decode(body)
        print(f"{CONSUMER}: headers={properties.headers} id={payload['messageId']}", flush=True)
        ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(queue=QUEUE, on_message_callback=handle, auto_ack=False)
    print(f"{CONSUMER}: binding headers={BINDING_HEADERS}", flush=True)
    channel.start_consuming()


if __name__ == "__main__":
    main()
