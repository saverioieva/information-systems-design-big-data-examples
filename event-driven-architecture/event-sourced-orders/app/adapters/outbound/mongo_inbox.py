"""MongoDB variant: one aggregate stream document is the atomic boundary.

Events and message IDs are appended in ONE conditional single-document write.
No multi-document transaction is required for this bounded classroom example.
For unbounded streams, use a collection of event documents plus a transaction
(on a replica set) or a different atomicity strategy.
"""
import os
from app.domain.idempotency import IncomingMessage


class MongoInboxEventStore:
    def __init__(self, uri: str | None = None):
        from pymongo import MongoClient
        self.client = MongoClient(uri or os.getenv('IDEMPOTENCY_MONGO_URI',
                                                   'mongodb://mongo:27017/'),
                                  serverSelectionTimeoutMS=5000, w='majority')
        self.client.admin.command('ping')
        self.collection = self.client['orders_es_demo']['demo_order_streams']

    def initialize(self):
        pass  # MongoDB creates the collection on first use.

    def accept(self, message: IncomingMessage) -> bool:
        self.collection.update_one({'_id': message.order_id},
            {'$setOnInsert': {'events': [], 'processedMessageIds': []}}, upsert=True)
        result = self.collection.update_one(
            {'_id': message.order_id, 'processedMessageIds': {'$ne': message.message_id}},
            {'$push': {'events': {'eventType': message.event_type, 'messageId': message.message_id}},
             '$addToSet': {'processedMessageIds': message.message_id}},
            upsert=False)
        return result.modified_count == 1

    def events(self, order_id: str) -> list[dict]:
        doc = self.collection.find_one({'_id': order_id}) or {}
        return [{'version': i + 1, **event} for i, event in enumerate(doc.get('events', []))]

    def close(self):
        self.client.close()
