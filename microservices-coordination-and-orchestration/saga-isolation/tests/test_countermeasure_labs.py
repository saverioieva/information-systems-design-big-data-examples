"""Fast tests for the two *separate* persisted countermeasure examples."""
import unittest
from fake_store import FakeSagaStore
from app.domain.isolation_policy import RISK_THRESHOLD, select_isolation_mode


class CountermeasureLabsTest(unittest.TestCase):
    def setUp(self):
        self.store = FakeSagaStore('orchestrator')

    def test_commutative_reordering_compensation_and_idempotent_replay(self):
        with self.store.transaction() as tx:
            tx.initialize_credit('a', 100)
            tx.initialize_credit('b', 100)
            tx.adjust_credit('a', 'a-credit', 25)
            a = tx.adjust_credit('a', 'a-debit', -10)
            tx.adjust_credit('b', 'b-debit', -10)
            b = tx.adjust_credit('b', 'b-credit', 25)
            self.assertEqual((a, b), (115, 115))
            self.assertEqual(tx.adjust_credit('a', 'a-credit', 25), 115)
            self.assertEqual(tx.adjust_credit('a', 'a-compensate', -25), 90)
            with self.assertRaisesRegex(ValueError, 'Conflicting duplicate'):
                tx.adjust_credit('a', 'a-credit', 26)

    def test_commutative_script_runs_with_storage_port(self):
        from app.demo_countermeasures import run_commutative
        from contextlib import redirect_stdout
        from io import StringIO
        output = StringIO()
        with redirect_stdout(output):
            run_commutative(self.store)
        self.assertIn('COMMUTATIVE: +25,-10 -> 115', output.getvalue())
        self.assertIn('compensation -25 -> 90', output.getvalue())

    def test_version_file_buffers_out_of_order_operations_and_replays_once(self):
        with self.store.transaction() as tx:
            self.assertEqual(tx.apply_versioned('s', 3, 'ADD', 7),
                             {'nextSequence': 1, 'total': 0, 'buffered': 1})
            self.assertEqual(tx.apply_versioned('s', 1, 'SET', 10),
                             {'nextSequence': 2, 'total': 10, 'buffered': 1})
        with self.store.transaction() as tx:
            self.assertEqual(tx.apply_versioned('s', 2, 'MULTIPLY', 2),
                             {'nextSequence': 4, 'total': 27, 'buffered': 0})
            self.assertEqual(tx.apply_versioned('s', 3, 'ADD', 7)['total'], 27)
            with self.assertRaisesRegex(ValueError, 'Conflicting duplicate'):
                tx.apply_versioned('s', 3, 'ADD', 99)
            with self.assertRaisesRegex(ValueError, 'positive'):
                tx.apply_versioned('s', 0, 'SET', 10)
            with self.assertRaisesRegex(ValueError, 'Unsupported'):
                tx.apply_versioned('s', 4, 'INVALID', 10)

    def test_by_value_policy_boundary(self):
        self.assertEqual(select_isolation_mode(RISK_THRESHOLD - 1), 'reread')
        self.assertEqual(select_isolation_mode(RISK_THRESHOLD), 'semantic')
        self.assertEqual(select_isolation_mode(RISK_THRESHOLD + 1), 'semantic')


if __name__ == '__main__':
    unittest.main()
