"""Business use cases tested with an in-memory UoW: no SQLAlchemy/Postgres needed."""
import unittest
from app.application.order_service import OrderService
from app.domain.models import ConcurrencyError


class FakeUnitOfWork:
    orders = {}
    events = []

    def __enter__(self):
        self.repo = self
        return self

    def __exit__(self, exc_type, exc, tb):
        pass

    def add_events(self, events):
        self.events.extend(events)

    def commit(self):
        pass

    def expire_all(self):
        pass

    def add(self, order):
        order.row_version = 1
        self.orders[order.id] = order

    def get(self, order_id):
        return self.orders.get(order_id)

    def save(self, order):
        order.row_version += 1
        self.orders[order.id] = order

    def delete(self, order_id):
        self.orders.pop(order_id, None)


class ApplicationUseCases(unittest.TestCase):
    def setUp(self):
        FakeUnitOfWork.orders = {}
        FakeUnitOfWork.events = []
        self.service = OrderService(FakeUnitOfWork)

    def test_create_and_change(self):
        created = self.service.create('cust', 'restaurant', [
            {'menu_item_id':'a', 'name':'Pizza', 'price':10.0, 'quantity':2}])
        self.assertEqual(created.order_total, 20)
        self.assertEqual(len(FakeUnitOfWork.events), 1)
        self.assertEqual(type(FakeUnitOfWork.events[0]).__name__, "OrderCreated")
        updated = self.service.add_item(created.id, 'a', 'Pizza', 10.0, 1, expected_version=1)
        self.assertEqual(updated.order_total, 30)
        self.assertEqual(updated.row_version, 2)
        with self.assertRaises(ConcurrencyError):
            self.service.add_item(created.id, 'a', 'Pizza', 10.0, 1, expected_version=1)

    def test_approve_generates_business_fact(self):
        created = self.service.create('cust', 'restaurant', [
            {'menu_item_id': 'x', 'name': 'Pizza', 'price': 15, 'quantity': 2}])
        approved = self.service.approve(created.id, expected_version=1)
        self.assertEqual(approved.state.value, 'APPROVED')
        self.assertEqual([type(e).__name__ for e in FakeUnitOfWork.events],
                         ['OrderCreated', 'OrderApproved'])
        with self.assertRaises(ValueError):
            self.service.approve(created.id)

    def test_delete(self):
        created = self.service.create('cust', 'restaurant', [
            {'menu_item_id':'a', 'name':'Pizza', 'price':10.0, 'quantity':1}])
        self.service.delete(created.id)
        self.assertIsNone(self.service.get(created.id))


if __name__ == '__main__':
    unittest.main()
