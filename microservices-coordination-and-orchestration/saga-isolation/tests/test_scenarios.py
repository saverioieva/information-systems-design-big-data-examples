import unittest
from demo.scenarios import (Order, cancel_naive, approve_naive, cancel_with_semantic_lock,
                            approve_with_reread, approve_with_version, apply_credit_delta,
                            SemanticLockError, StaleReadError)

class SagaIsolationTests(unittest.TestCase):
    def test_lost_update(self):
        order=Order(); cancel_naive(order); approve_naive(order)
        self.assertEqual(order.state,'APPROVED') # demonstrates the bug
    def test_semantic_lock(self):
        with self.assertRaises(SemanticLockError): cancel_with_semantic_lock(Order())
    def test_reread(self):
        order=Order();cancel_naive(order)
        self.assertFalse(approve_with_reread(order))
        self.assertEqual(order.state,'CANCELLED')
    def test_version(self):
        order=Order();v=order.version;cancel_naive(order)
        with self.assertRaises(StaleReadError): approve_with_version(order,v)
    def test_commutativity(self):
        self.assertEqual(apply_credit_delta(apply_credit_delta(100,10),-5),
                         apply_credit_delta(apply_credit_delta(100,-5),10))

if __name__=='__main__':unittest.main()
