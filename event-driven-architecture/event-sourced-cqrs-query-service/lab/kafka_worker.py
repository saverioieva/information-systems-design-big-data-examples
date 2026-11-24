"""Order History Service's Kafka consumer: one durable group and explicit commits."""
from __future__ import annotations

import json
import logging
import os
import threading

from confluent_kafka import Consumer, KafkaException

log = logging.getLogger(__name__)


class HistoryStreamWorker:
    def __init__(self, store):
        self.store = store
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, name="history-kafka-consumer", daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        self.thread.join(timeout=8)

    def _run(self):
        bootstrap = os.getenv("KAFKA_BOOTSTRAP", "kafka:19092")
        topic = os.getenv("KAFKA_TOPIC", "orders.integration")
        group = os.getenv("KAFKA_GROUP_ID", "order-history-view")
        while not self.stop_event.is_set():
            consumer = None
            try:
                consumer = Consumer({
                    "bootstrap.servers": bootstrap,
                    "group.id": group,
                    "auto.offset.reset": "earliest",
                    "enable.auto.commit": False,
                    "enable.auto.offset.store": False,
                })
                consumer.subscribe([topic])
                while not self.stop_event.is_set():
                    record = consumer.poll(1.0)
                    if record is None:
                        continue
                    if record.error():
                        raise KafkaException(record.error())
                    envelope = json.loads(record.value())
                    # Do not advance past a failed event: retry that SAME record.
                    while not self.stop_event.is_set():
                        try:
                            self.store.project(envelope)
                            consumer.commit(message=record, asynchronous=False)
                            break
                        except Exception:
                            log.exception("MongoDB projection/commit failed; retrying Kafka record")
                            self.stop_event.wait(1)
            except Exception:
                if not self.stop_event.is_set():
                    log.exception("Kafka history worker reconnecting")
                    self.stop_event.wait(2)
            finally:
                if consumer is not None:
                    consumer.close()
