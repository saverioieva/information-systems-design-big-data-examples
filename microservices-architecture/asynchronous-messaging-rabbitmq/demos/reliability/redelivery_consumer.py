import argparse
import os

from demos.common import connection, decode


QUEUE = "reliability.redelivery"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--crash-before-ack", action="store_true")
    args = parser.parse_args()

    conn = connection()
    channel = conn.channel()
    channel.queue_declare(queue=QUEUE, durable=True)
    channel.basic_qos(prefetch_count=1)

    def handle(ch, method, properties, body: bytes) -> None:
        payload = decode(body)
        print(
            f"received order={payload['orderId']} redelivered={method.redelivered} id={properties.message_id}",
            flush=True,
        )
        if args.crash_before_ack:
            print("simulating consumer crash BEFORE ACK", flush=True)
            os._exit(3)
        print("processing completed -> ACK", flush=True)
        ch.basic_ack(delivery_tag=method.delivery_tag)
        ch.stop_consuming()

    channel.basic_consume(queue=QUEUE, on_message_callback=handle, auto_ack=False)
    channel.start_consuming()
    conn.close()


if __name__ == "__main__":
    main()
