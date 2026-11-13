import unittest
from app.application.order_service import OrderService


class FakeStore:
    def __init__(self):
        self.rows = {}
        self.events = []

    def create(self, order_id, amount, event):
        self.rows[order_id] = {'amount':amount,'status':'CREATED'}
        self.events.append(event)

    def approve(self, order_id, event_factory):
        if order_id not in self.rows or self.rows[order_id]['status'] != 'CREATED':
            raise ValueError('invalid state')
        row = self.rows[order_id]
        row['status'] = 'APPROVED'
        event = event_factory('OrderApproved',order_id,row['amount'],'APPROVED').as_dict()
        self.events.append(event)
        return event


class OrderUseCaseTests(unittest.TestCase):
    def test_fact_changes_on_approval(self):
        fake = FakeStore()
        service = OrderService(fake)
        created = service.create(4.5)
        approved = service.approve(created['orderId'])
        self.assertEqual([x['type'] for x in fake.events], ['OrderCreated','OrderApproved'])
        self.assertEqual(approved['eventId'], fake.events[1]['eventId'])
        with self.assertRaises(ValueError):
            service.approve(created['orderId'])
        self.assertEqual(len(fake.events), 2)


if __name__ == '__main__':
    unittest.main()
