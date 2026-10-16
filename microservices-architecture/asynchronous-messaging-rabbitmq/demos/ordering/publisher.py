from demos.common import connection, encode, persistent_json_properties


EXCHANGE = "orders.partitioned"


def main() -> None:
    conn = connection()
    channel = conn.channel()
    channel.exchange_declare(exchange=EXCHANGE, exchange_type="direct", durable=True)

    events = ["created", "paid", "accepted"]
    for sequence, event in enumerate(events, start=1):
        for order_key in ("A", "B"):
            payload = {
                "orderId": f"order-{order_key}",
                "sequence": sequence,
                "event": event,
            }
            channel.basic_publish(
                exchange=EXCHANGE,
                routing_key=f"order.{order_key}",
                body=encode(payload),
                properties=persistent_json_properties(),
            )
            print(f"published order={order_key} sequence={sequence} event={event}")

    conn.close()


if __name__ == "__main__":
    main()
