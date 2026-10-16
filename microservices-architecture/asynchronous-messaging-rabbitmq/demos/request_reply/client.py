import argparse
import uuid

from demos.common import connection, decode, encode, persistent_json_properties


QUEUE = "pricing.rpc"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--order-id", default="order-123")
    parser.add_argument("--subtotal", type=float, default=25.0)
    args = parser.parse_args()

    conn = connection()
    channel = conn.channel()
    channel.queue_declare(queue=QUEUE, durable=True)
    callback = channel.queue_declare(queue="", exclusive=True, auto_delete=True)
    callback_queue = callback.method.queue

    correlation_id = str(uuid.uuid4())
    response: dict | None = None

    def on_reply(ch, method, properties, body: bytes) -> None:
        nonlocal response
        if properties.correlation_id == correlation_id:
            response = decode(body)

    channel.basic_consume(queue=callback_queue, on_message_callback=on_reply, auto_ack=True)
    request = {"orderId": args.order_id, "subtotal": args.subtotal}
    channel.basic_publish(
        exchange="",
        routing_key=QUEUE,
        body=encode(request),
        properties=persistent_json_properties(
            correlation_id=correlation_id,
            reply_to=callback_queue,
        ),
    )
    print(f"client: sent request corr={correlation_id} reply_to={callback_queue}")

    while response is None:
        conn.process_data_events(time_limit=1)

    print(f"client: matched reply corr={correlation_id} -> {response}")
    conn.close()


if __name__ == "__main__":
    main()
