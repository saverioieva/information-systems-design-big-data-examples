import os
import tempfile
import unittest

from app.adapters.outbound.sqlite_repository import create_order, get_order, init_db, record_validation
from app.domain.order import order_status
from app.domain.validation import validate


class OrderProcessingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["DB_PATH"] = os.path.join(self.tmp.name, "test.sqlite")
        init_db()
        create_order("ORD-1", "CUST-1", "pizza")

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("DB_PATH", None)

    def test_pending_then_validated(self):
        self.assertEqual(get_order("ORD-1")["status"], "PENDING")
        self.assertEqual(record_validation("ORD-1", "consumer", True)["status"], "PENDING")
        self.assertEqual(record_validation("ORD-1", "restaurant", True)["status"], "VALIDATED")

    def test_rejected_if_either_validation_fails(self):
        self.assertEqual(record_validation("ORD-1", "consumer", False)["status"], "REJECTED")
        self.assertEqual(record_validation("ORD-1", "restaurant", True)["status"], "REJECTED")

    def test_duplicate_result_is_idempotent(self):
        record_validation("ORD-1", "consumer", True)
        record_validation("ORD-1", "restaurant", True)
        after = record_validation("ORD-1", "consumer", False)
        self.assertEqual(after["status"], "VALIDATED")
        self.assertEqual(after["consumer_check"], "PASS")

    def test_other_order_is_unaffected(self):
        create_order("ORD-2", "CUST-2", "salad")
        record_validation("ORD-1", "consumer", True)
        self.assertEqual(get_order("ORD-2")["status"], "PENDING")

    def test_both_validation_scenarios(self):
        self.assertTrue(validate("consumer", {"consumer_id": "CUST-1"}))
        self.assertFalse(validate("consumer", {"consumer_id": "blocked"}))
        self.assertTrue(validate("restaurant", {"item": "pizza"}))
        self.assertFalse(validate("restaurant", {"item": "unavailable"}))


if __name__ == "__main__":
    unittest.main()
