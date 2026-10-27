import unittest
from app.domain.models import Order, OrderLineItem, OrderState

class OrderAggregateTests(unittest.TestCase):
    def make_order(self):
        return Order.create("CUST_1","REST_1",[OrderLineItem("PIZZA","Pizza",10.0,2)])
    def test_root_creates_consistent_order(self):
        order=self.make_order()
        self.assertEqual(order.order_total,20.0)
        order.add_item_to_order("PIZZA","Pizza",10.0,1)
        self.assertEqual(order.order_total,30.0)
    def test_aggregate_generates_domain_event_without_event_sourcing(self):
        order = self.make_order()
        events = order.collect_domain_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].aggregate_type, "Order")
        self.assertEqual(events[0].aggregate_id, order.id)
        self.assertEqual(events[0].amount, order.order_total)
        self.assertEqual(order.collect_domain_events(), [])
        # Current state is still represented by the aggregate, not a replayed event log.
        self.assertEqual(order.order_total, 20.0)

    def test_rejects_empty_order(self):
        with self.assertRaises(ValueError): Order.create("A","B",[])
    def test_rejects_invalid_item(self):
        with self.assertRaises(ValueError): OrderLineItem("X","x",10.0,-1)
        with self.assertRaises(ValueError): OrderLineItem("X","x",-1.0,1)
    def test_invariant_after_approval(self):
        order=self.make_order();order.state=OrderState.APPROVED
        with self.assertRaises(ValueError): order.add_item_to_order("PASTA","Pasta",3.0,1)
        with self.assertRaises(ValueError): order.remove_item_from_order("PIZZA")

if __name__=="__main__": unittest.main()
