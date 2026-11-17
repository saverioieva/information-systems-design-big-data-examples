"""Order use cases depend on an OrderStore port, never on a database or web API."""
from app.ports.order_store import OrderStore

class OrderService:
    def __init__(self, store: OrderStore):
        self.store = store

    def create_order(self, consumer_id, restaurant_id, items):
        order_id = self.store.create_order(consumer_id, restaurant_id, items)
        return self.store.get_order(order_id)

    def get_order(self, order_id):
        return self.store.get_order(order_id)

    def get_order_version(self, order_id, version):
        return self.store.get_order_version(order_id, version)

    def add_item_to_order(self, order_id, menu_item_id, name, price, quantity, expected_version=None):
        self.store.add_item_to_order(order_id, menu_item_id, name, price, quantity, expected_version)
        return self.store.get_order(order_id)

    def approve_order(self, order_id, expected_version=None):
        self.store.approve_order(order_id, expected_version)
        return self.store.get_order(order_id)

    def cancel_order(self, order_id, expected_version=None):
        self.store.cancel_order(order_id, expected_version)
        return self.store.get_order(order_id)
