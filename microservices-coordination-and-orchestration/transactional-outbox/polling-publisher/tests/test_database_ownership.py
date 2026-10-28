"""Guard against accidentally reintroducing cross-service database access."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DatabaseOwnershipTests(unittest.TestCase):
    def test_separate_postgres_containers_and_volumes(self):
        compose = (ROOT / 'docker-compose.yml').read_text()
        self.assertIn('postgres_order:', compose)
        self.assertIn('postgres_audit:', compose)
        self.assertIn('postgres_order_data:', compose)
        self.assertIn('postgres_audit_data:', compose)
        self.assertIn('@postgres_order:5432/orders', compose)
        self.assertIn('@postgres_audit:5432/audit', compose)

    def test_order_schema_and_api_do_not_read_audit_data(self):
        order_db = (ROOT / 'app/adapters/outbound/postgres_repository.py').read_text()
        api = (ROOT / 'app/main.py').read_text()
        self.assertNotIn('received_events', order_db)
        self.assertNotIn("@app.get('/received')", api)
        self.assertIn('CREATE TABLE IF NOT EXISTS received_events',
                      (ROOT / 'app/adapters/outbound/postgres_audit_repository.py').read_text())

    def test_audit_consumer_depends_only_on_its_repository(self):
        consumer = (ROOT / 'app/adapters/inbound/audit_consumer.py').read_text()
        self.assertIn('PostgresAuditRepository', consumer)
        self.assertNotIn('PostgresOutboxRepository', consumer)
        makefile = (ROOT / 'Makefile').read_text()
        self.assertIn('exec -T postgres_audit psql', makefile)


if __name__ == '__main__':
    unittest.main()
