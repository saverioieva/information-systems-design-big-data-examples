"""Pure domain decisions across saga participants; no broker or database needed."""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def policy(role):
    path = ROOT / role / 'domain' / 'policy.py'
    spec = importlib.util.spec_from_file_location(role + '_policy', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ParticipantRules(unittest.TestCase):
    def test_order_approval(self):
        rules = policy('order_service')
        self.assertEqual(rules.status_for_accounting_event('accounting.creditCardAuthorized'), 'APPROVED')
        self.assertEqual(rules.status_for_accounting_event('accounting.creditCardAuthorizationFailed'), 'REJECTED')

    def test_consumer_eligibility(self):
        rules = policy('consumer_service')
        self.assertTrue(rules.can_order(True))
        self.assertFalse(rules.can_order(False))

    def test_kitchen_ticket_state(self):
        rules = policy('kitchen_service')
        self.assertEqual(rules.ticket_state('order.created'), 'CREATE_PENDING')
        self.assertEqual(rules.ticket_state('accounting.creditCardAuthorized'), 'TICKET_ACCEPTED')
        self.assertEqual(rules.ticket_state('accounting.creditCardAuthorizationFailed'), 'REJECTED')

    def test_accounting_pivot_rule(self):
        rules = policy('accounting_service')
        self.assertTrue(rules.can_authorize(100.0))
        self.assertFalse(rules.can_authorize(100.01))


if __name__ == '__main__':
    unittest.main()
