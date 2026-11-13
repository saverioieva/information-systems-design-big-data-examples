"""Application use cases: aggregate emits facts, UoW commits state and notifications."""
from app.domain.models import Order, OrderLineItem, ConcurrencyError


class OrderService:
    def __init__(self, uow_factory):
        self.uow_factory = uow_factory

    def create(self, consumer_id, restaurant_id, items):
        with self.uow_factory() as uow:
            order = Order.create(
                consumer_id=consumer_id,
                restaurant_id=restaurant_id,
                items=[OrderLineItem(**item) for item in items],
            )
            uow.repo.add(order)
            # The domain model knows nothing about PostgreSQL or messaging.
            # Outgoing integration intents share the local database transaction.
            uow.add_events(order.collect_domain_events())
            uow.commit()
            uow.expire_all()
            return uow.repo.get(order.id)

    def get(self, order_id):
        with self.uow_factory() as uow:
            return uow.repo.get(order_id)

    def add_item(self, order_id, menu_item_id, name, price, quantity, expected_version=None):
        with self.uow_factory() as uow:
            order = uow.repo.get(order_id)
            if order is None:
                raise LookupError("Order not found")
            if expected_version is not None and expected_version != order.row_version:
                raise ConcurrencyError("Stale expected_version; reload the order")
            order.add_item_to_order(menu_item_id, name, price, quantity)
            uow.repo.save(order)
            uow.commit()
            uow.expire_all()
            return uow.repo.get(order.id)

    def approve(self, order_id, expected_version=None):
        with self.uow_factory() as uow:
            order = uow.repo.get(order_id)
            if order is None:
                raise LookupError("Order not found")
            if expected_version is not None and expected_version != order.row_version:
                raise ConcurrencyError("Stale expected_version; reload the order")
            order.approve()
            uow.repo.save(order)
            uow.add_events(order.collect_domain_events())
            uow.commit()
            uow.expire_all()
            return uow.repo.get(order.id)

    def delete(self, order_id):
        with self.uow_factory() as uow:
            if uow.repo.get(order_id) is None:
                raise LookupError("Order not found")
            uow.repo.delete(order_id)
            uow.commit()
            return {"status": "deleted", "order_id": order_id}

    def delete_item(self, order_id, menu_item_id):
        with self.uow_factory() as uow:
            order = uow.repo.get(order_id)
            if order is None:
                raise LookupError("Order not found")
            order.remove_item_from_order(menu_item_id)
            uow.repo.save(order)
            uow.commit()
            uow.expire_all()
            return uow.repo.get(order.id)
