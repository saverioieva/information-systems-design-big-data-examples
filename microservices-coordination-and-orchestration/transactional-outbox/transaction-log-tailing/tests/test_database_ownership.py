"""Database per Service invariants and the Audit delivery application port."""
from pathlib import Path
import unittest

from app.application.use_cases import AuditDeliveryHandler

ROOT = Path(__file__).resolve().parents[1]


class FakeAuditStore:
    def __init__(self):
        self.received = {}

    def record_received(self, event_id, order_id):
        self.received.setdefault(event_id, order_id)


class AuditOwnershipTests(unittest.TestCase):
    def test_handler_uses_audit_store_and_is_idempotent(self):
        repo = FakeAuditStore()
        handler = AuditDeliveryHandler(repo)
        body = b'{"eventId":"evt1","type":"OrderCreated","orderId":"ord1","amount":42}'
        self.assertEqual(handler.handle_delivery(body)['orderId'], 'ord1')
        handler.handle_delivery(body)
        self.assertEqual(repo.received, {'evt1': 'ord1'})

    def test_two_postgres_instances_and_separate_schemas(self):
        compose = (ROOT / 'docker-compose.yml').read_text()
        self.assertIn('postgres_order:', compose)
        self.assertIn('postgres_audit:', compose)
        self.assertIn('postgres_order_data:', compose)
        self.assertIn('postgres_audit_data:', compose)
        self.assertIn('@postgres_order:5432/orders', compose)
        self.assertIn('@postgres_audit:5432/audit', compose)
        self.assertNotIn('received_events', (ROOT / 'db/001_schema.sql').read_text())
        self.assertIn('CREATE TABLE received_events',
                      (ROOT / 'db/002_audit_schema.sql').read_text())

    def test_order_service_not_reading_consumer_database(self):
        self.assertNotIn('received_events',
                         (ROOT / 'app/adapters/outbound/postgres_repository.py').read_text())
        self.assertNotIn("@app.get('/received')", (ROOT / 'app/main.py').read_text())
        consumer = (ROOT / 'app/adapters/inbound/rabbitmq_consumer.py').read_text()
        self.assertIn('PostgresAuditRepository', consumer)
        self.assertNotIn('PostgresOrderRepository', consumer)
        self.assertIn('exec -T postgres_audit psql', (ROOT / 'Makefile').read_text())


if __name__ == '__main__':
    unittest.main()
