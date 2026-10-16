import argparse
import uuid

from demos.common import connection, encode, persistent_json_properties


EXCHANGE = "orders.direct"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("routing_key", choices=["order.created", "order.failed"])
    parser.add_argument("--order-id", default="order-123")
    args = parser.parse_args()

    payload = {
        "type": "OrderCreated" if args.routing_key == "order.created" else "OrderFailed",
        "eventId": str(uuid.uuid4()),
        "orderId": args.order_id,
    }

    conn = connection()
    channel = conn.channel()
    channel.exchange_declare(exchange=EXCHANGE, exchange_type="direct", durable=True)
    channel.basic_publish(
        exchange=EXCHANGE,
        routing_key=args.routing_key,
        body=encode(payload),
        properties=persistent_json_properties(message_id=payload["eventId"]),
    )
    print(f"published key={args.routing_key} order={args.order_id}")
    conn.close()


if __name__ == "__main__":
    main()
