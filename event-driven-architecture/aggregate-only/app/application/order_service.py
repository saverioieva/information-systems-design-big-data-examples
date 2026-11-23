"""Use cases; no FastAPI or SQLAlchemy dependency."""
from typing import Callable
from app.domain.models import Order, OrderLineItem
from app.ports.unit_of_work import OrderUnitOfWork

class OrderNotFound(LookupError):
    pass

class OrderService:
    def __init__(self, uow_factory: Callable[[], OrderUnitOfWork]):
        self.uow_factory = uow_factory

    def create(self, consumer_id: str, restaurant_id: str, items: list[OrderLineItem]) -> Order:
        order = Order.create(consumer_id, restaurant_id, items)
        with self.uow_factory() as uow:
            uow.orders.add(order)
            uow.commit()
            return uow.orders.get(order.id)

    def get(self, order_id: str) -> Order:
        with self.uow_factory() as uow:
            order = uow.orders.get(order_id)
            if order is None:
                raise OrderNotFound(order_id)
            return order

    def update(self, order_id: str, operation, expected_version: int | None = None) -> Order:
        with self.uow_factory() as uow:
            order = uow.orders.get(order_id)
            if order is None:
                raise OrderNotFound(order_id)
            if expected_version is not None and order.row_version != expected_version:
                from app.domain.models import ConcurrencyError
                raise ConcurrencyError("Version mismatch")
            operation(order)
            uow.orders.save(order)  # atomic SQL compare-and-swap (version = expected)
            uow.commit()
            return uow.orders.get(order_id)

    def add_item(self, order_id, menu_item_id, name, price, quantity, expected_version=None):
        return self.update(order_id, lambda o: o.add_item_to_order(menu_item_id, name, price, quantity), expected_version)

    def approve(self, order_id, expected_version=None):
        return self.update(order_id, lambda o: o.approve(), expected_version)

    def cancel(self, order_id, expected_version=None):
        return self.update(order_id, lambda o: o.cancel(), expected_version)
