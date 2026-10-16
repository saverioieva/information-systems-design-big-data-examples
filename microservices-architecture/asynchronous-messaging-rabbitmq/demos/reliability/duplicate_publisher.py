import uuid

from demos.common import connection, encode, persistent_json_properties


EXCHANGE = "payments.direct"


def publish(channel, message_id: str, order_id: str) -> None:
    payload = {"type": "AuthorizePayment", "orderId": order_id}
    channel.basic_publish(
        exchange=EXCHANGE,
        routing_key="payment.authorize",
        body=encode(payload),
        properties=persistent_json_properties(message_id=message_id),
    )
    print(f"published order={order_id} id={message_id}")


def main() -> None:
    conn = connection()
    channel = conn.channel()
    channel.exchange_declare(exchange=EXCHANGE, exchange_type="direct", durable=True)

    duplicate_id = str(uuid.uuid4())
    publish(channel, duplicate_id, "order-duplicate")
    publish(channel, duplicate_id, "order-duplicate")
    publish(channel, str(uuid.uuid4()), "order-unique")
    conn.close()


if __name__ == "__main__":
    main()
