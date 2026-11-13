"""Business use cases; storage adapter owns transaction boundary."""
from uuid import uuid4
from app.domain.events import new_event


class OrderService:
    def __init__(self, store):
        self.store = store

    def create(self, amount: float) -> dict:
        if amount <= 0:
            raise ValueError("amount must be positive")
        order_id = str(uuid4())
        event = new_event('OrderCreated', order_id, amount, 'CREATED')
        self.store.create(order_id, amount, event.as_dict())
        return event.as_dict()

    def approve(self, order_id: str) -> dict:
        return self.store.approve(order_id, new_event)
