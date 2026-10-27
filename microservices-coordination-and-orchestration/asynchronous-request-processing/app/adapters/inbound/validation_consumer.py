"""Run with WORKER_ROLE=consumer or WORKER_ROLE=restaurant."""
from __future__ import annotations

import json
import logging
import os
import time

from app.domain.validation import validate
from app.adapters.outbound.rabbitmq import (
    CONSUMER_QUEUE, RESTAURANT_QUEUE, RESULTS_QUEUE,
    configure_channel, connect_with_retry, publish_json,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOG = logging.getLogger(__name__)


def main():
    role = os.getenv("WORKER_ROLE", "consumer")
    if role not in ("consumer", "restaurant"):
        raise ValueError(f"Unknown role {role}")
    queue = CONSUMER_QUEUE if role == "consumer" else RESTAURANT_QUEUE
    connection = connect_with_retry()
    channel = configure_channel(connection)
    channel.basic_qos(prefetch_count=1)

    def callback(ch, method, properties, body):
        try:
            request = json.loads(body)
            if request["type"] not in ("ValidateConsumer", "ValidateOrderDetails"):
                raise ValueError("Unexpected message type")
            for field in ("order_id", "consumer_id", "item"):
                if not isinstance(request.get(field), str):
                    raise ValueError(f"Missing field {field}")
        except (ValueError, KeyError, TypeError) as exc:
            LOG.error("Rejecting invalid message: %s", exc)
            ch.basic_reject(delivery_tag=method.delivery_tag, requeue=False)
            return

        time.sleep(float(os.getenv("VALIDATION_DELAY_SECONDS", "2")))
        ok = validate(role, request)
        result = {
            "type": f"{role.title()}Validated" if ok else f"{role.title()}Rejected",
            "order_id": request["order_id"],
            "validation": role,
            "ok": ok,
        }
        try:
            # Publish a confirmed reply before acknowledging the request.
            publish_json(ch, RESULTS_QUEUE, result)
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception:
            LOG.exception("Failed publishing result; request may be redelivered")
            if ch.is_open:
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            raise
        LOG.info("[flow] order=%s %s_validation=%s", request["order_id"], role, "PASS" if ok else "FAIL")

    channel.basic_consume(queue=queue, on_message_callback=callback, auto_ack=False)
    LOG.info("Waiting for %s requests on %s", role, queue)
    channel.start_consuming()


if __name__ == "__main__":
    main()
