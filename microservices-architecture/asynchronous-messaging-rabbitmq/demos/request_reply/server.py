from decimal import Decimal

from demos.common import connection, decode, encode, persistent_json_properties


QUEUE = "pricing.rpc"


def main() -> None:
    conn = connection()
    channel = conn.channel()
    channel.queue_declare(queue=QUEUE, durable=True)
    channel.basic_qos(prefetch_count=1)

    def handle(ch, method, properties, body: bytes) -> None:
        request = decode(body)
        subtotal = Decimal(str(request["subtotal"]))
        delivery_fee = Decimal("4.50")
        response = {
            "orderId": request["orderId"],
            "subtotal": float(subtotal),
            "deliveryFee": float(delivery_fee),
            "total": float(subtotal + delivery_fee),
        }
        print(
            f"server: request order={request['orderId']} corr={properties.correlation_id}",
            flush=True,
        )
        ch.basic_publish(
            exchange="",
            routing_key=properties.reply_to,
            body=encode(response),
            properties=persistent_json_properties(correlation_id=properties.correlation_id),
        )
        ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(queue=QUEUE, on_message_callback=handle, auto_ack=False)
    print(f"pricing RPC server waiting on {QUEUE}", flush=True)
    channel.start_consuming()


if __name__ == "__main__":
    main()
