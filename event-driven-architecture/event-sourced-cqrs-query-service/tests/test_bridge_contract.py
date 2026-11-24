"""Verifies the Kafka stream contract without starting a broker."""

from lab.stream_bridge import publish_and_wait


class FakeKafkaRecord:
    def __init__(self):
        self.keys = []
        self.values = []
        self.callbacks = []

    def produce(self, topic, key, value, on_delivery):
        self.keys.append((topic, key))
        self.values.append(value)
        self.callbacks.append(on_delivery)

    def flush(self, timeout):
        for done in self.callbacks:
            done(None, None)
        return 0


def test_bridge_keys_kafka_records_by_order_id():
    fake = FakeKafkaRecord()
    publish_and_wait(fake, "orders.integration", {"order_id": "order-17", "type": "integration.order.created"})
    assert fake.keys == [("orders.integration", b"order-17")]
    assert b'integration.order.created' in fake.values[0]
