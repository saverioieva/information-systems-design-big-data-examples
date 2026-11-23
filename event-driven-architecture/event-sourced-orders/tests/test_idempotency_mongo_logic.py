"""Offline simulation of the bounded atomic Mongo event stream document."""
from types import SimpleNamespace
from app.domain.idempotency import IncomingMessage, rebuild
from app.adapters.outbound.mongo_inbox import MongoInboxEventStore


class OneDocumentCollection:
    def __init__(self):
        self.value = None

    def update_one(self, query, update, upsert=False):
        if self.value is None and upsert:
            self.value = {'_id': query['_id'], **update['$setOnInsert']}
            return SimpleNamespace(modified_count=0)
        if self.value is None or query['_id'] != self.value['_id']:
            return SimpleNamespace(modified_count=0)
        duplicate_id = query.get('processedMessageIds',{}).get('$ne')
        if duplicate_id in self.value['processedMessageIds']:
            return SimpleNamespace(modified_count=0)
        if '$push' in update:
            self.value['events'].append(update['$push']['events'])
            self.value['processedMessageIds'].append(update['$addToSet']['processedMessageIds'])
            return SimpleNamespace(modified_count=1)
        return SimpleNamespace(modified_count=0)

    def find_one(self, selector):
        if self.value is not None and selector['_id'] == self.value['_id']:
            return self.value
        return None


def test_same_delivery_twice_appends_only_one_event():
    backend = object.__new__(MongoInboxEventStore)
    backend.collection = OneDocumentCollection()
    messages = [IncomingMessage('m1','o1','OrderCreated'), IncomingMessage('m2','o1','OrderApproved')]
    for message in messages:
        assert backend.accept(message)
        assert not backend.accept(message)
    events = backend.events('o1')
    assert len(events) == 2
    assert rebuild(events) == 'APPROVED'
