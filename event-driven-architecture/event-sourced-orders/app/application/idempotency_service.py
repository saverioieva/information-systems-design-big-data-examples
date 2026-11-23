"""Use case for at-least-once message delivery with exactly-once local effects."""
from app.domain.idempotency import IncomingMessage, rebuild
from app.ports.message_inbox import MessageInboxEventStore

class IdempotentEventConsumer:
    def __init__(self, storage: MessageInboxEventStore):
        self.storage = storage

    def handle(self, message: IncomingMessage) -> dict:
        accepted = self.storage.accept(message)
        events = self.storage.events(message.order_id)
        return {"accepted": accepted, "eventCount": len(events), "state": rebuild(events)}
