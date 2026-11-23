"""Outbound adapter around the eventsourcing framework application.

Library-specific not-found exceptions never escape to the application layer.
"""
from eventsourcing.application import AggregateNotFoundError
from app.application.errors import OrderNotFound
from app.adapters.outbound.eventsourcing_application import OrderApplication

class EventsourcingOrderStore:
    def __init__(self, event_app: OrderApplication | None = None):
        self._events = event_app if event_app is not None else OrderApplication()

    def _call(self, fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except AggregateNotFoundError as exc:
            raise OrderNotFound("Order or historic version not found") from exc

    def create_order(self, consumer_id, restaurant_id, items):
        return self._call(self._events.create_order, consumer_id, restaurant_id, items)

    def get_order(self, order_id):
        return self._call(self._events.get_order, order_id)

    def get_order_version(self, order_id, version):
        return self._call(self._events.get_order_version, order_id, version)

    def add_item_to_order(self, order_id, menu_item_id, name, price, quantity, expected_version=None):
        return self._call(self._events.add_item_to_order, order_id, menu_item_id, name, price, quantity, expected_version)

    def approve_order(self, order_id, expected_version=None):
        return self._call(self._events.approve_order, order_id, expected_version)

    def cancel_order(self, order_id, expected_version=None):
        return self._call(self._events.cancel_order, order_id, expected_version)
