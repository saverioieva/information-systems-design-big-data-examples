"""Publish messages using AMQP 1.0 with Apache Qpid Proton."""

import argparse
import json
import uuid

from proton import Message

from demos.amqp10.settings import ADDRESS, connect


def main():
    parser = argparse.ArgumentParser(description="AMQP 1.0 order-event publisher")
    parser.add_argument("--count", type=int, default=3)
    args = parser.parse_args()
    if args.count < 1:
        parser.error("--count must be positive")

    conn = connect()
    try:
        sender = conn.create_sender(ADDRESS)
        try:
            for index in range(1, args.count + 1):
                payload = {
                    "eventId": f"proton-{uuid.uuid4().hex[:8]}",
                    "orderId": f"order-amqp10-{index:03d}",
                    "type": "order.created",
                    "source": "proton-amqp-1.0",
                }
                message = Message(
                    body=json.dumps(payload),
                    content_type="application/json",
                    durable=True,
                    id=payload["eventId"],
                )
                # BlockingSender.send waits for broker settlement / outcome;
                # it does not mean an application consumer has processed it.
                sender.send(message)
                print(f"[Proton AMQP 1.0] sent to {ADDRESS}: {payload}", flush=True)
        finally:
            sender.close()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
