import argparse

import pika

from demos.common import connection, encode, persistent_json_properties


QUEUE = "orders.work"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=8)
    args = parser.parse_args()

    conn = connection()
    channel = conn.channel()
    channel.queue_declare(queue=QUEUE, durable=True)

    for number in range(1, args.count + 1):
        payload = {
            "type": "CreateOrderTask",
            "orderId": f"order-{number:03d}",
            "workSeconds": 0.4 + (number % 3) * 0.3,
        }
        channel.basic_publish(
            exchange="",
            routing_key=QUEUE,
            body=encode(payload),
            properties=persistent_json_properties(),
        )
        print(f"sent {payload['orderId']} work={payload['workSeconds']:.1f}s")

    conn.close()


if __name__ == "__main__":
    main()
