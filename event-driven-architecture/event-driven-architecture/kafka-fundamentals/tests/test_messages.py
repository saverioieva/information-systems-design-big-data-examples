import unittest
from app.domain.messages import example_message, serialize_event, parse_event
from app.application.publish_example import produce_examples


class FakeProducer:
    def __init__(self):
        self.records = []
        self.flushed = False

    def send(self, *, key, value):
        self.records.append((key, parse_event(value)))

    def flush(self):
        self.flushed = True


class MessagesTests(unittest.TestCase):
    def test_key_is_order_id_for_stable_partition_selection(self):
        producer = FakeProducer()
        ids = produce_examples(producer, count=12)
        self.assertEqual(len(ids), 12)
        self.assertEqual(len(set(ids)), 12)
        self.assertEqual([k for k, v in producer.records[:4]],
                         ['DEMO-00', 'DEMO-01', 'DEMO-02', 'DEMO-03'])
        self.assertEqual(producer.records[0][0], producer.records[4][0])
        self.assertTrue(producer.flushed)

    def test_serialization(self):
        event = example_message(5, prefix='O')
        self.assertEqual(parse_event(serialize_event(event))['orderId'], 'O-01')

    def test_bad_message(self):
        with self.assertRaises(ValueError):
            parse_event(b'{}')


if __name__ == '__main__':
    unittest.main()
