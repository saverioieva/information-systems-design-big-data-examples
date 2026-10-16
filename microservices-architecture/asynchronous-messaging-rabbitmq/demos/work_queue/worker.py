import os
import time

from demos.common import connection, decode


QUEUE = "orders.work"
WORKER_NAME = os.getenv("WORKER_NAME", "worker")


def main() -> None:
    conn = connection()
    channel = conn.channel()
    channel.queue_declare(queue=QUEUE, durable=True)
    channel.basic_qos(prefetch_count=1)

    def handle(ch, method, properties, body: bytes) -> None:
        payload = decode(body)
        print(f"{WORKER_NAME}: received {payload['orderId']}", flush=True)
        time.sleep(float(payload["workSeconds"]))
        print(f"{WORKER_NAME}: completed {payload['orderId']} -> ACK", flush=True)
        ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(queue=QUEUE, on_message_callback=handle, auto_ack=False)
    print(f"{WORKER_NAME}: waiting on {QUEUE}; prefetch=1", flush=True)
    channel.start_consuming()


if __name__ == "__main__":
    main()
