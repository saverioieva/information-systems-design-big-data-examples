"""Pure adapter-independent mapping from integration event to routing key."""
from dataclasses import dataclass
import json


EVENT_ROUTING = {'OrderCreated': 'order.created', 'OrderApproved': 'order.approved'}


@dataclass(frozen=True)
class RoutedEvent:
    event_id: str
    routing_key: str
    payload: bytes


def decode_outbox_value(value: bytes) -> dict:
    """Handle a JSON object (and Debezium's optional JSON-string representation)."""
    result = json.loads(value.decode('utf-8'))
    if isinstance(result, str):
        result = json.loads(result)
    if not isinstance(result, dict):
        raise ValueError('Outbox record must be a JSON object')
    return result


def translate(value: bytes) -> RoutedEvent:
    event = decode_outbox_value(value)
    event_type = event.get('type')
    if event_type not in EVENT_ROUTING:
        raise ValueError(f'Unknown event type: {event_type}')
    if not event.get('eventId') or not event.get('orderId'):
        raise ValueError('Missing eventId or orderId')
    return RoutedEvent(event_id=event['eventId'], routing_key=EVENT_ROUTING[event_type],
                       payload=json.dumps(event, separators=(',', ':')).encode('utf-8'))
