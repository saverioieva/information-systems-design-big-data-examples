"""Business use cases and relay algorithm with ports only."""
import os
from app.domain.order import new_order
from app.ports.repositories import OutboxRepository
from app.ports.publisher import MessagePublisher
from app.ports.audit_repository import AuditRepository

class OutboxUseCases:
    def __init__(self, repo: OutboxRepository):
        self.repo = repo
    def create(self, amount: float) -> dict:
        event = new_order(amount)
        self.repo.save_order_and_message(event)
        return event.message()
    def get_order(self, order_id: str) -> dict | None:
        return self.repo.find_order(order_id)
    def get_outbox(self) -> list[dict]:
        return self.repo.outbox_rows()

class PollingRelay:
    def __init__(self, repo: OutboxRepository, publisher: MessagePublisher):
        self.repo, self.publisher = repo, publisher
    def publish_once(self) -> bool:
        row = self.repo.pending()
        if row is None:
            return False
        self.publisher.publish(row['routing_key'], row['payload'], row['event_id'])
        # Demonstrate at-least-once: crash after publish confirmation => replay.
        if os.getenv('CRASH_AFTER_CONFIRM') == '1':
            os._exit(30)
        self.repo.mark_sent(row['event_id'])
        return True

class AuditHandler:
    def __init__(self, repo: AuditRepository): self.repo = repo
    def handle(self, event: dict) -> None:
        self.repo.record_delivery(event['eventId'], event['orderId'])
