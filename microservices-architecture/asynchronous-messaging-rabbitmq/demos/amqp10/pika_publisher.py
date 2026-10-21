"""Optional interoperability demo: Pika/AMQP 0-9-1 -> Proton/AMQP 1.0."""

import json
import uuid

from demos.amqp10.settings import QUEUE_NAME
from demos.common import connection, persistent_json_properties


def main():
    payload = {
        "eventId": f"pika-{uuid.uuid4().hex[:8]}",
        "orderId": "order-cross-protocol-001",
        "type": "order.created",
        "source": "pika-amqp-0-9-1",
    }
    conn = connection()
    try:
        channel = conn.channel()
        channel.confirm_delivery()
        channel.basic_publish(
            exchange="",
            routing_key=QUEUE_NAME,
            body=json.dumps(payload).encode("utf-8"),
            properties=persistent_json_properties(message_id=payload["eventId"]),
            mandatory=True,
        )
        print(f"[Pika AMQP 0-9-1] published to {QUEUE_NAME}: {payload}", flush=True)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
