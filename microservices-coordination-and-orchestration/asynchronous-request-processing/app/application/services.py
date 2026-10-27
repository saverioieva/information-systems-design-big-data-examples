"""Application use cases: dependencies point only at ports."""
from app.ports.repository import OrderRepository
from app.ports.messaging import ValidationPublisher

class OrderUseCases:
    def __init__(self, orders: OrderRepository, publisher: ValidationPublisher):
        self.orders, self.publisher = orders, publisher

    def create_order(self, order_id: str, consumer_id: str, item: str) -> dict:
        self.orders.create(order_id, consumer_id, item)
        # Deliberate dual-write gap: the next Transactional Outbox lab fixes this.
        self.publisher.publish_requests(order_id, consumer_id, item)
        return {"order_id": order_id, "status": "PENDING", "status_url": f"/orders/{order_id}"}

    def order(self, order_id: str) -> dict | None:
        return self.orders.get(order_id)

    def validation_result(self, order_id: str, source: str, ok: bool) -> dict | None:
        return self.orders.record_validation(order_id, source, ok)
