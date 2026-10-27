"""Business message decoding without any messaging SDK dependencies."""
import json

def decode_message(body: bytes) -> dict:
    """Accept normal JSON and a JSON-encoded string from the value converter."""
    value = json.loads(body)
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict):
        raise ValueError("Expected OrderCreated JSON object")
    if value.get("type") != "OrderCreated" or not value.get("eventId") or not value.get("orderId"):
        raise ValueError(f"Unexpected outbox content: {value!r}")
    return value
