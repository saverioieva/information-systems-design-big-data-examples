import argparse
import uuid

from demos.common import connection, encode, persistent_json_properties


EXCHANGE = "orders.topic"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("routing_key", choices=["order.created", "order.updated", "order.failed"])
    parser.add_argument("--order-id", default="order-123")
    args = parser.parse_args()

    payload = {
        "type": args.routing_key,
        "eventId": str(uuid.uuid4()),
        "orderId": args.order_id,
    }

    conn = connection()
    channel = conn.channel()
    channel.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)
    channel.basic_publish(
        exchange=EXCHANGE,
        routing_key=args.routing_key,
        body=encode(payload),
        properties=persistent_json_properties(message_id=payload["eventId"]),
    )
    print(f"published {args.routing_key}")
    conn.close()


if __name__ == "__main__":
    main()
