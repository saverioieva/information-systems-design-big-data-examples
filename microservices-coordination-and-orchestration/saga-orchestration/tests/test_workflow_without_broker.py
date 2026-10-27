"""End-to-end state transitions with real SQLite adapters and a simulated transport.

No RabbitMQ/Docker needed: messages are read from each participant's durable
outbox and passed to the next service's application handler.
"""
import json
import tempfile
import unittest
from pathlib import Path

from app.adapters.outbound.sqlite_store import SqliteSagaStore
from app.application.use_cases import SagaUseCases


class SagaWorkflowTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.stores = {}
        self.services = {}
        for role in ('orchestrator', 'consumer', 'kitchen', 'accounting'):
            store = SqliteSagaStore(role, str(Path(self.temp.name) / (role + '.sqlite')))
            store.initialize()
            self.stores[role] = store
            self.services[role] = SagaUseCases(store, role)

    def tearDown(self):
        self.temp.cleanup()

    def drain(self):
        destinations = {'command.consumer': 'consumer',
                        'command.kitchen': 'kitchen',
                        'command.accounting': 'accounting',
                        'reply.orchestrator': 'orchestrator'}
        for _ in range(50):
            dispatched = 0
            for role, store in self.stores.items():
                msg = store.pending()
                if msg:
                    recipient = destinations[msg['routing_key']]
                    self.services[recipient].handle_message(json.loads(msg['payload']))
                    store.mark_sent(msg['event_id'])
                    dispatched += 1
            if dispatched == 0:
                return
        raise AssertionError('Saga did not converge')

    def test_happy_path(self):
        created = self.services['orchestrator'].place_order('CUST_OK', 25)
        self.drain()
        row = self.services['orchestrator'].get_order(created['orderId'])
        self.assertEqual(row['status'], 'APPROVED')
        self.assertEqual(row['stage'], 'APPROVED')

    def test_declined_card_compensates(self):
        created = self.services['orchestrator'].place_order('CUST_OK', 150)
        self.drain()
        row = self.services['orchestrator'].get_order(created['orderId'])
        self.assertEqual(row['status'], 'REJECTED')
        with self.stores['kitchen'].transaction() as tx:
            ticket = tx.db.execute('SELECT state FROM tickets WHERE order_id=?', (created['orderId'],)).fetchone()
            self.assertEqual(ticket['state'], 'REJECTED')

    def test_reject_before_kitchen(self):
        created = self.services['orchestrator'].place_order('CUST_INVALID', 25)
        self.drain()
        row = self.services['orchestrator'].get_order(created['orderId'])
        self.assertEqual(row['stage'], 'REJECTED')
        with self.stores['kitchen'].transaction() as tx:
            self.assertEqual(tx.db.execute('SELECT COUNT(*) FROM tickets').fetchone()[0], 0)

    def test_duplicate_reply_is_idempotent(self):
        created = self.services['orchestrator'].place_order('CUST_OK', 25)
        request = self.stores['orchestrator'].pending()
        message = json.loads(request['payload'])
        self.services['consumer'].handle_message(message)
        self.services['consumer'].handle_message(message)
        with self.stores['consumer'].transaction() as tx:
            self.assertEqual(tx.db.execute('SELECT COUNT(*) FROM outbox').fetchone()[0], 1)


if __name__ == '__main__':
    unittest.main()
