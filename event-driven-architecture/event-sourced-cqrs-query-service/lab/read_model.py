"""MongoDB Order History read model.

An order and its per-source version checkpoints live in ONE Mongo document.
One conditional document update atomically records each delivered Integration
Event ID, evolves current state for new versions and appends a history entry.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import os

from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

from lab.projection_rules import changes_for


class QueryStore:
    def __init__(self, uri: str | None = None, client: Any | None = None):
        self.client = client if client is not None else MongoClient(
            uri or os.getenv("MONGODB_URI", "mongodb://history-db:27017/"),
            serverSelectionTimeoutMS=2500,
        )
        self.database = self.client[os.getenv("MONGODB_DATABASE", "order_history")]
        self.orders = self.database["order_history"]

    def ensure_schema(self) -> None:
        self.client.admin.command("ping")
        self.orders.create_index("consumer_id")

    def project(self, envelope: dict[str, Any]) -> bool:
        """Record each message once and update state only for newer source versions.

        Kafka and RabbitMQ can redeliver events. Ordering is tracked PER source
        Aggregate (order/accounting/kitchen), never across independent services.
        """
        kind = envelope["type"]
        if not kind.startswith("integration."):
            raise ValueError(f"Not an integration event: {kind}")
        source = envelope["source"]
        if source not in ("order", "accounting", "kitchen"):
            raise ValueError(f"Unknown integration event source: {source}")
        order_id = envelope["order_id"]
        version = int(envelope["version"])
        if version <= 0:
            raise ValueError("Source version must be positive")
        changes = changes_for(kind, envelope.get("data", {}))
        timeline_entry = {
            "message_id": envelope["message_id"],
            "source": source,
            "source_version": version,
            "event_type": kind,
        }
        for _ in range(20):
            current = self.orders.find_one({"_id": order_id})
            if current is None:
                try:
                    self.orders.insert_one({
                        "_id": order_id,
                        "consumer_id": None,
                        "restaurant_id": None,
                        "total": None,
                        "order_status": "UNKNOWN",
                        "payment_status": "NOT_STARTED",
                        "kitchen_status": "NOT_STARTED",
                        "source_versions": {},
                        "timeline": [],
                        "processed_message_ids": [],
                        "revision": 0,
                        "updated_at": datetime.now(timezone.utc),
                    })
                except DuplicateKeyError:
                    pass  # Another concurrent worker created this document.
                continue
            if envelope["message_id"] in current.get("processed_message_ids", []):
                return False
            seen = int(current.get("source_versions", {}).get(source, 0))
            set_fields = {"updated_at": datetime.now(timezone.utc)}
            if version > seen:
                set_fields.update(changes)
                set_fields[f"source_versions.{source}"] = version
            elif kind == "integration.order.created":
                # Late creation facts can still populate immutable order metadata
                # without rolling an already APPROVED/CANCELLED status backwards.
                for field in ("consumer_id", "restaurant_id", "total"):
                    if current.get(field) is None:
                        set_fields[field] = changes[field]
            update = {
                "$set": set_fields,
                "$addToSet": {"processed_message_ids": envelope["message_id"]},
                "$push": {"timeline": timeline_entry},
                "$inc": {"revision": 1},
            }
            result = self.orders.update_one(
                {"_id": order_id, "revision": current["revision"]}, update
            )
            if result.modified_count:
                return True
        raise RuntimeError("Concurrent MongoDB projection updates did not converge")

    def find_order(self, order_id: str) -> dict[str, Any] | None:
        document = self.orders.find_one({"_id": order_id})
        if document is None:
            return None
        return {
            "order_id": document["_id"],
            "consumer_id": document.get("consumer_id"),
            "restaurant_id": document.get("restaurant_id"),
            "total": document.get("total"),
            "order_status": document.get("order_status"),
            "payment_status": document.get("payment_status"),
            "kitchen_status": document.get("kitchen_status"),
            "updated_at": document["updated_at"].isoformat(),
            "source_versions": document.get("source_versions", {}),
        }

    def history(self, order_id: str) -> dict[str, Any] | None:
        current = self.find_order(order_id)
        if current is None:
            return None
        doc = self.orders.find_one({"_id": order_id}, {"timeline": 1})
        # Arrival order, not a global causal order across independent services.
        return {**current, "timeline": doc.get("timeline", [])}

    def reset(self) -> None:
        """Lab-only: delete derived MongoDB documents, never source events."""
        self.orders.delete_many({})

    def stats(self) -> dict[str, int]:
        return {"orders": self.orders.count_documents({}),
                "projected_events": sum(len(doc.get("timeline", []))
                                        for doc in self.orders.find({}, {"timeline": 1}))}
