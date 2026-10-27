"""Pure application logic: turn committed outbox INSERTs into outgoing messages."""
import json
from typing import Any
from app.contract import decode_message
from app.ports.publisher import EventPublisher


def extract_outbox_messages(raw_change: str | bytes) -> list[dict[str, Any]]:
    """Decode wal2json v1's *committed transaction* batch.

    Ignore changes to other tables and non-INSERT operations. The authoritative
    Order state remains in `orders`; only outgoing intents are published.
    """
    batch = json.loads(raw_change)
    result = []
    for change in batch.get("change", []):
        if (change.get("kind"), change.get("schema"), change.get("table")) != (
            "insert", "public", "outbox_events"
        ):
            continue
        fields = dict(zip(change["columnnames"], change["columnvalues"]))
        payload = fields["payload"]
        if isinstance(payload, dict):
            payload = json.dumps(payload)
        if not isinstance(payload, (str, bytes)):
            raise ValueError("Outbox payload must contain a JSON object")
        event = decode_message(payload)
        if (str(fields["event_id"]) != event["eventId"]
                or str(fields["aggregate_id"]) != event["orderId"]
                or fields["event_type"] != event["type"]):
            raise ValueError("Outbox row fields disagree with the message payload")
        result.append(event)
    return result


class LogTailRelay:
    def __init__(self, publisher: EventPublisher):
        self.publisher = publisher

    def process_transaction(self, raw_change: str | bytes) -> int:
        """Raise on publish failure: the WAL position MUST NOT be acknowledged."""
        messages = extract_outbox_messages(raw_change)
        for event in messages:
            self.publisher.publish(event)
        return len(messages)
