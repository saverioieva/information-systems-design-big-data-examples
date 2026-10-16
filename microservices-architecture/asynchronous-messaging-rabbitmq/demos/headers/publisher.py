import argparse
import uuid

from demos.common import connection, encode, persistent_json_properties


EXCHANGE = "orders.headers"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", choices=["order", "payment"], required=True)
    parser.add_argument("--region", choices=["eu", "us"], required=True)
    args = parser.parse_args()

    message_id = str(uuid.uuid4())
    payload = {"messageId": message_id, "description": f"{args.type} message for {args.region}"}
    headers = {"type": args.type, "region": args.region}

    conn = connection()
    channel = conn.channel()
    channel.exchange_declare(exchange=EXCHANGE, exchange_type="headers", durable=True)
    channel.basic_publish(
        exchange=EXCHANGE,
        routing_key="ignored.by.headers.exchange",
        body=encode(payload),
        properties=persistent_json_properties(message_id=message_id, headers=headers),
    )
    print(f"published headers={headers}")
    conn.close()


if __name__ == "__main__":
    main()
