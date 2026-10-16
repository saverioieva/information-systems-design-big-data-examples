import sqlite3

from demos.common import connection, decode


EXCHANGE = "payments.direct"
QUEUE = "payment.authorize"
DB_PATH = "/data/processed_messages.db"


def main() -> None:
    database = sqlite3.connect(DB_PATH)
    database.execute(
        "CREATE TABLE IF NOT EXISTS processed_messages (message_id TEXT PRIMARY KEY)"
    )
    database.commit()

    conn = connection()
    channel = conn.channel()
    channel.exchange_declare(exchange=EXCHANGE, exchange_type="direct", durable=True)
    channel.queue_declare(queue=QUEUE, durable=True)
    channel.queue_bind(exchange=EXCHANGE, queue=QUEUE, routing_key="payment.authorize")
    channel.basic_qos(prefetch_count=1)

    def handle(ch, method, properties, body: bytes) -> None:
        payload = decode(body)
        message_id = properties.message_id
        if not message_id:
            raise ValueError("message_id is required for idempotency demo")

        row = database.execute(
            "SELECT 1 FROM processed_messages WHERE message_id = ?", (message_id,)
        ).fetchone()
        if row:
            print(f"duplicate -> SKIP id={message_id}", flush=True)
        else:
            print(f"new -> authorize order={payload['orderId']} id={message_id}", flush=True)
            database.execute(
                "INSERT INTO processed_messages(message_id) VALUES (?)", (message_id,)
            )
            database.commit()
        ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(queue=QUEUE, on_message_callback=handle, auto_ack=False)
    print(f"idempotent consumer waiting on {QUEUE}; db={DB_PATH}", flush=True)
    channel.start_consuming()


if __name__ == "__main__":
    main()
