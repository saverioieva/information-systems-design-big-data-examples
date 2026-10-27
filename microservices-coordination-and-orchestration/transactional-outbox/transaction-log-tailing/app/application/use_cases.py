"""Inbound HTTP/RabbitMQ adapters call these use cases."""
from app.domain.order import new_order
from app.ports.repository import OrderRepository
from app.contract import decode_message

class OutboxUseCases:
    def __init__(self, repo: OrderRepository): self.repo=repo
    def create(self,amount:float) -> dict:
        order = new_order(amount)
        self.repo.save_and_enqueue(order)
        return order.as_message()
    def get_order(self,oid:str) -> dict | None: return self.repo.find_order(oid)
    def get_outbox(self) -> list[dict]: return self.repo.outbox_rows()
    def get_received(self) -> list[dict]: return self.repo.received_rows()
    def handle_delivery(self, payload: bytes) -> dict:
        message = decode_message(payload)
        self.repo.record_received(message['eventId'],message['orderId'])
        return message
