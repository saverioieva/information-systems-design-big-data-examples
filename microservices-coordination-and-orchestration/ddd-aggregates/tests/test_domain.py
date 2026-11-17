import unittest
from dataclasses import FrozenInstanceError
from decimal import Decimal

from app.domain.models import (
    Address, Money, Order, OrderLine, OrderLineDraft, OrderState
)
from tests.common import address, line, order


class EntityTests(unittest.TestCase):
    def test_order_lines_have_distinct_identity_even_with_same_values(self):
        first, second = OrderLine.from_draft(line()), OrderLine.from_draft(line())
        self.assertNotEqual(first, second)
        self.assertEqual(first.unit_price, second.unit_price)

    def test_quantity_change_keeps_entity_identity(self):
        aggregate = order()
        before = aggregate.lines[0]
        aggregate.change_line_quantity(before.line_id, 3)
        after = aggregate.lines[0]
        self.assertEqual(before.line_id, after.line_id)
        self.assertEqual(before, after)  # equality by entity ID, not attributes
        self.assertNotEqual(before.quantity, after.quantity)
        self.assertEqual(after.quantity, 3)

    def test_other_aggregates_are_referenced_only_by_ids(self):
        aggregate = order()
        self.assertEqual(aggregate.consumer_id, 'CUST_1')
        self.assertEqual(aggregate.restaurant_id, 'REST_1')
        self.assertIsInstance(aggregate.consumer_id, str)


class ValueObjectTests(unittest.TestCase):
    def test_money_uses_value_equality_and_decimal(self):
        self.assertEqual(Money('10.00'), Money(Decimal('10'), 'eur'))
        self.assertEqual((Money('5.00') + Money('2.00')).amount, Decimal('7.00'))
        self.assertEqual(Money('5.00').times(3).amount, Decimal('15.00'))

    def test_money_rejects_invalid_values_and_currency_mismatch(self):
        for amount in ('-1', '1.234', 'NaN'):
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                Money(amount)
        with self.assertRaises(ValueError):
            Money('1.00', 'EUR') + Money('1.00', 'USD')

    def test_address_uses_value_equality_and_is_immutable(self):
        self.assertEqual(address(), Address('Via Roma 1', 'Bari', '70100', 'IT'))
        with self.assertRaises(FrozenInstanceError):
            address().city = 'Lecce'
        with self.assertRaises(ValueError):
            Address('', 'Bari', '70100', 'IT')


class BoundaryTests(unittest.TestCase):
    def test_child_collection_is_read_only(self):
        aggregate = order()
        self.assertIsInstance(aggregate.lines, tuple)
        with self.assertRaises(AttributeError):
            aggregate.lines.append(line())

    def test_child_entity_is_immutable_outside_root(self):
        aggregate = order()
        with self.assertRaises(FrozenInstanceError):
            aggregate.lines[0].quantity = 9
        self.assertEqual(aggregate.lines[0].quantity, 2)

    def test_root_state_and_address_cannot_be_assigned_directly(self):
        aggregate = order()
        with self.assertRaises(AttributeError):
            aggregate.state = OrderState.APPROVED
        with self.assertRaises(AttributeError):
            aggregate.address = address()
        with self.assertRaises(AttributeError):
            aggregate.row_version = 123

    def test_address_is_replaced_only_through_root(self):
        aggregate = order()
        initial = address()
        aggregate.change_delivery_address(initial)
        self.assertEqual(aggregate.address, initial)
        with self.assertRaises(FrozenInstanceError):
            aggregate.address.street = 'Another Street'
        replacement = Address('Corso Italia 9', 'Bari', '70100', 'IT')
        aggregate.change_delivery_address(replacement)
        self.assertEqual(aggregate.address, replacement)


class InvariantTests(unittest.TestCase):
    def test_empty_and_duplicate_line_are_rejected(self):
        with self.assertRaises(ValueError):
            Order.create('C', 'R', [])
        with self.assertRaises(ValueError):
            Order.create('C', 'R', [line(), line()])

    def test_quantity_and_currency_invariants(self):
        with self.assertRaises(ValueError):
            line(qty=0)
        with self.assertRaises(ValueError):
            Order.create('C', 'R', [line(), line('TEA', currency='USD')])

    def test_total_cap_is_checked_across_multiple_entities(self):
        aggregate = Order.create('C', 'R', [line(qty=10)])
        self.assertEqual(aggregate.total.amount, Decimal('100.00'))
        with self.assertRaisesRegex(ValueError, 'exceeds'):
            aggregate.add_line(line('EXPENSIVE', price='120.00', qty=1))
        self.assertEqual(len(aggregate.lines), 1)
        self.assertEqual(aggregate.total.amount, Decimal('100.00'))

    def test_failed_quantity_change_does_not_corrupt_aggregate(self):
        aggregate = order()
        line_id = aggregate.lines[0].line_id
        aggregate.collect_domain_events()
        with self.assertRaises(ValueError):
            aggregate.change_line_quantity(line_id, 30)
        self.assertEqual(aggregate.lines[0].quantity, 2)
        self.assertEqual(aggregate.collect_domain_events(), [])

    def test_last_line_cannot_be_removed(self):
        aggregate = order()
        with self.assertRaises(ValueError):
            aggregate.remove_line(aggregate.lines[0].line_id)
        self.assertEqual(len(aggregate.lines), 1)

    def test_approval_requires_address_and_minimum_total(self):
        aggregate = order()
        with self.assertRaisesRegex(ValueError, 'address'):
            aggregate.approve()
        aggregate.change_delivery_address(address())
        aggregate.approve()
        self.assertEqual(aggregate.state, OrderState.APPROVED)
        inexpensive = Order.create('C', 'R', [line(price='2.00')])
        inexpensive.change_delivery_address(address())
        with self.assertRaisesRegex(ValueError, 'at least'):
            inexpensive.approve()

    def test_approved_order_cannot_be_modified(self):
        aggregate = order()
        aggregate.change_delivery_address(address())
        aggregate.approve()
        with self.assertRaises(ValueError):
            aggregate.change_line_quantity(aggregate.lines[0].line_id, 3)
        with self.assertRaises(ValueError):
            aggregate.change_delivery_address(Address('X', 'Y', 'Z', 'IT'))

    def test_cancelled_order_cannot_be_approved(self):
        aggregate = order()
        aggregate.cancel()
        with self.assertRaises(ValueError):
            aggregate.approve()
        self.assertEqual(aggregate.state, OrderState.CANCELLED)


class DomainEventTests(unittest.TestCase):
    def test_create_and_approve_emit_business_facts_with_metadata(self):
        aggregate = order()
        events = aggregate.collect_domain_events()
        self.assertEqual([type(event).__name__ for event in events], ['OrderCreated'])
        self.assertEqual(events[0].aggregate_type, 'Order')
        self.assertEqual(events[0].aggregate_id, aggregate.id)
        self.assertTrue(events[0].event_id)
        self.assertTrue(events[0].occurred_at)
        aggregate.change_delivery_address(address())
        aggregate.approve()
        self.assertEqual([type(event).__name__ for event in aggregate.collect_domain_events()],
                         ['DeliveryAddressChanged', 'OrderApproved'])

    def test_root_creates_events_for_child_updates(self):
        aggregate = order()
        aggregate.collect_domain_events()
        aggregate.add_line(line('WATER', '2.00'))
        new_line = next(item for item in aggregate.lines if item.menu_item_id == 'WATER')
        aggregate.change_line_quantity(new_line.line_id, 3)
        aggregate.remove_line(new_line.line_id)
        self.assertEqual([type(event).__name__ for event in aggregate.collect_domain_events()],
                         ['OrderLineAdded', 'OrderLineQuantityChanged', 'OrderLineRemoved'])

    def test_no_op_address_update_creates_no_event(self):
        aggregate = order()
        aggregate.collect_domain_events()
        aggregate.change_delivery_address(address())
        aggregate.collect_domain_events()
        aggregate.change_delivery_address(address())
        self.assertEqual(aggregate.collect_domain_events(), [])


if __name__ == '__main__':
    unittest.main()
