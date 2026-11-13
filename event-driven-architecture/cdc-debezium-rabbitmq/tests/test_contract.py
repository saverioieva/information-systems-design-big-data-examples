"""Static contract tests for WAL, connector topology and the Outbox split."""
import json
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


class CDCContractTests(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads((ROOT / 'connector/orders-raw.json').read_text())['config']
        self.out = json.loads((ROOT / 'connector/outbox-postgres.json').read_text())['config']
        self.sql = (ROOT / 'db/001_schema.sql').read_text()
        self.store = (ROOT / 'app/adapters/outbound/postgres_store.py').read_text()

    def test_publications_and_separate_replication_slots(self):
        self.assertEqual(self.raw['plugin.name'], 'pgoutput')
        self.assertEqual(self.out['plugin.name'], 'pgoutput')
        self.assertIn('CREATE PUBLICATION raw_orders_publication', self.sql)
        self.assertIn('CREATE PUBLICATION integration_outbox_publication', self.sql)
        self.assertNotEqual(self.raw['slot.name'], self.out['slot.name'])
        self.assertEqual(self.raw['table.include.list'], 'public.orders')
        self.assertEqual(self.out['table.include.list'], 'public.outbox_events')

    def test_outbox_router_and_append_only(self):
        self.assertEqual(self.out['transforms.outbox.type'], 'io.debezium.transforms.outbox.EventRouter')
        self.assertEqual(self.out['transforms.outbox.table.expand.json.payload'], 'true')
        self.assertEqual(self.out['transforms.outbox.route.topic.replacement'], 'orders.integration')
        self.assertIn('with self.engine.begin()', self.store)
        self.assertNotIn('UPDATE outbox_events', self.store)
        self.assertNotIn('DELETE FROM outbox_events', self.store)


if __name__ == '__main__':
    unittest.main()
