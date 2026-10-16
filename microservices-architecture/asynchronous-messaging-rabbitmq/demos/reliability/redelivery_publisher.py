import uuid

from demos.common import connection, encode, persistent_json_properties


QUEUE = "reliability.redelivery"


def main() -> None:
    conn = connection()
    channel = conn.channel()
    channel.queue_declare(queue=QUEUE, durable=True)
    channel.queue_purge(queue=QUEUE)
    message_id = str(uuid.uuid4())
    channel.basic_publish(
        exchange="",
        routing_key=QUEUE,
        body=encode({"type": "OrderCreated", "orderId": "order-redelivery"}),
        properties=persistent_json_properties(message_id=message_id),
    )
    print(f"published one persistent message id={message_id}")
    conn.close()


if __name__ == "__main__":
    main()
