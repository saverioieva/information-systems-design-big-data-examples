"""Order Service's separate reply consumer updates the order's current state."""
from __future__ import annotations

import json
import logging

from app.application.services import OrderUseCases
from app.adapters.outbound.sqlite_repository import SqliteOrderRepository
from app.adapters.outbound.rabbitmq import RabbitMQValidationPublisher
from app.adapters.outbound.rabbitmq import RESULTS_QUEUE, configure_channel, connect_with_retry

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOG = logging.getLogger(__name__)


def main():
    orders = SqliteOrderRepository()
    orders.initialize()
    service = OrderUseCases(orders, RabbitMQValidationPublisher())
    connection = connect_with_retry()
    channel = configure_channel(connection)
    channel.basic_qos(prefetch_count=1)

    def callback(ch, method, properties, body):
        try:
            result = json.loads(body)
            order_id = result["order_id"]
            source = result["validation"]
            ok = result["ok"]
            if not isinstance(order_id, str) or source not in ("consumer", "restaurant") or not isinstance(ok, bool):
                raise ValueError("Unexpected result fields")
        except (ValueError, KeyError, TypeError) as exc:
            LOG.error("Rejecting malformed validation result: %s", exc)
            ch.basic_reject(delivery_tag=method.delivery_tag, requeue=False)
            return

        try:
            row = service.validation_result(order_id, source, ok)
        except Exception:
            LOG.exception("DB commit failed; result will be retried")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            return
        ch.basic_ack(delivery_tag=method.delivery_tag)
        if row is None:
            LOG.warning("No order found for validation result %s", order_id)
        else:
            LOG.info("[flow] order=%s consumer=%s restaurant=%s status=%s",
                     order_id, row["consumer_check"], row["restaurant_check"], row["status"])

    channel.basic_consume(queue=RESULTS_QUEUE, on_message_callback=callback, auto_ack=False)
    LOG.info("Listening for validation results on %s", RESULTS_QUEUE)
    channel.start_consuming()


if __name__ == "__main__":
    main()
