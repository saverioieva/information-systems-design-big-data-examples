
"""Isolated AMQP topology/handler tests: no Docker, RabbitMQ, or PostgreSQL."""
import importlib.util
import os
from pathlib import Path
import runpy
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class FakeAMQPError(Exception):
    pass


class Channel:
    def __init__(self):
        self.exchanges = []
        self.queues = []
        self.bindings = []
        self.acks = []
        self.nacks = []
        self.consumer = None
        self.events = []

    def exchange_declare(self, **kwargs):
        self.exchanges.append(kwargs)

    def queue_declare(self, **kwargs):
        self.queues.append(kwargs)
        return types.SimpleNamespace(method=types.SimpleNamespace(queue=kwargs['queue']))

    def queue_bind(self, **kwargs):
        self.bindings.append(kwargs)

    def basic_qos(self, **kwargs):
        pass

    def basic_consume(self, **kwargs):
        self.consumer = kwargs['on_message_callback']

    def basic_ack(self, delivery_tag):
        self.acks.append(delivery_tag)

    def basic_nack(self, delivery_tag, requeue):
        self.nacks.append((delivery_tag, requeue))

    def start_consuming(self):
        for i, (body, route) in enumerate(self.events, 1):
            props = types.SimpleNamespace(message_id='msg-%s' % i)
            method = types.SimpleNamespace(delivery_tag=i, routing_key=route)
            self.consumer(self, method, props, body)
        raise StopIteration('stop test loop')


class Connection:
    is_open = True

    def __init__(self, channel):
        self.ch = channel
        self.closed = False

    def channel(self):
        return self.ch

    def close(self):
        self.closed = True


pika = types.ModuleType('pika')
pika.exceptions = types.SimpleNamespace(AMQPError=FakeAMQPError)
pika.URLParameters = lambda url: url
pika.BlockingConnection = lambda params: Connection(Channel())


class MessagingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The messaging module declares metadata but does not open a DB connection.
        os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')
        with patch.dict(sys.modules, {'pika': pika}):
            spec = importlib.util.spec_from_file_location('saga_shared_test', ROOT / 'libs/saga_common/saga_common/__init__.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        cls.shared = module

    def test_backoff_is_capped(self):
        self.assertAlmostEqual(self.shared.retry_delay(1), self.shared.RETRY_BASE)
        self.assertLessEqual(self.shared.retry_delay(50), self.shared.RETRY_MAXS)
        self.assertGreaterEqual(self.shared.retry_delay(3), self.shared.retry_delay(2))

    def test_queue_and_matching_dead_letter_queue(self):
        ch = Channel()
        q = self.shared.declare_and_bind(ch, 'consumer.q', ['order.created'])
        self.assertEqual(q, 'consumer.q')
        configured = next(item for item in ch.queues if item['queue'] == 'consumer.q')
        self.assertEqual(configured['arguments'], {
            'x-dead-letter-exchange': 'saga.dlx',
            'x-dead-letter-routing-key': 'consumer.q',
        })
        self.assertTrue(any(x['queue'] == 'consumer.q.dlq' for x in ch.queues))
        self.assertIn({'exchange': 'saga.dlx', 'queue': 'consumer.q.dlq', 'routing_key': 'consumer.q'}, ch.bindings)

    def test_ack_after_handler_and_nack_bad_message(self):
        ch = Channel()
        conn = Connection(ch)
        ch.events = [
            (b'{"messageId":"m-ok","orderId":"o-ok"}', 'consumer.verified'),
            (b'{"messageId":"m-bad","orderId":"o-bad"}', 'consumer.verified'),
        ]
        processed = []

        def handler(event, properties, route):
            if event['orderId'] == 'o-bad':
                raise ValueError('intentional poison message')
            processed.append(event['orderId'])

        with patch.object(self.shared, '_connect', return_value=(conn, ch)):
            with self.assertRaises(StopIteration):
                self.shared.run_consumer('accounting_service', 'accounting.q', ['consumer.verified'], handler)
        self.assertEqual(processed, ['o-ok'])
        self.assertEqual(ch.acks, [1])
        self.assertEqual(ch.nacks, [(2, False)])
        self.assertTrue(conn.closed)

    def test_topology_creates_five_service_dlqs(self):
        ch = Channel()
        conn = Connection(ch)
        with patch.dict(sys.modules, {'pika': pika}):
            with patch.object(pika, 'BlockingConnection', return_value=conn):
                runpy.run_path(str(ROOT / 'topology.py'), run_name='__main__')
        primaries = [q for q in ch.queues if not q['queue'].endswith('.dlq')]
        dead = [q for q in ch.queues if q['queue'].endswith('.dlq')]
        self.assertEqual(len(primaries), 5)
        self.assertEqual(len(dead), 5)
        for q in primaries:
            name = q['queue']
            self.assertEqual(q['arguments']['x-dead-letter-routing-key'], name)
            self.assertTrue(any(d['queue'] == name + '.dlq' for d in dead))
        self.assertTrue(conn.closed)


if __name__ == '__main__':
    unittest.main()
