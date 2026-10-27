"""Validate the application layer with fake outbound adapters (no DB/broker)."""
import unittest
from app.application.use_cases import OutboxUseCases, PollingRelay, AuditHandler

class MemoryRepository:
    def __init__(self):
        self.events = []
        self.sent = []
        self.received = set()
    def save_order_and_message(self, event): self.events.append(event)
    def pending(self):
        for event in self.events:
            if event.event_id not in self.sent:
                return {'event_id': event.event_id,
                        'routing_key': 'order.created', 'payload': event.message()}
        return None
    def mark_sent(self, event_id): self.sent.append(event_id)
    def record_delivery(self, eid, oid): self.received.add((eid, oid))

class FakePublisher:
    def __init__(self, fail=False): self.messages=[]; self.fail=fail
    def publish(self, route, body, event_id):
        if self.fail: raise RuntimeError('broker offline')
        self.messages.append((route, body, event_id))

class HexagonalOutboxTests(unittest.TestCase):
    def test_order_command_stores_publication_intent(self):
        repo = MemoryRepository()
        created = OutboxUseCases(repo).create(42)
        self.assertEqual(created['type'], 'OrderCreated')
        self.assertEqual(len(repo.events), 1)

    def test_successful_confirm_marks_as_sent(self):
        repo, publisher = MemoryRepository(), FakePublisher()
        created = OutboxUseCases(repo).create(42)
        relay = PollingRelay(repo,publisher)
        self.assertTrue(relay.publish_once())
        self.assertEqual(repo.sent, [created['eventId']])
        self.assertFalse(relay.publish_once())

    def test_failed_publisher_leaves_pending(self):
        repo = MemoryRepository()
        OutboxUseCases(repo).create(42)
        with self.assertRaises(RuntimeError): PollingRelay(repo,FakePublisher(fail=True)).publish_once()
        self.assertEqual(repo.sent, [])

    def test_audit_is_idempotent(self):
        repo = MemoryRepository()
        handler = AuditHandler(repo)
        handler.handle({'eventId':'e1','orderId':'o1'})
        handler.handle({'eventId':'e1','orderId':'o1'})
        self.assertEqual(len(repo.received), 1)

if __name__=='__main__':unittest.main()
