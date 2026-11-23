"""A small message contract for the independent Event Sourcing Inbox demonstration."""
from dataclasses import dataclass

TYPES = {'OrderCreated', 'OrderApproved'}


@dataclass(frozen=True)
class IncomingMessage:
    message_id: str
    order_id: str
    event_type: str

    def __post_init__(self):
        if not self.message_id or not self.order_id or self.event_type not in TYPES:
            raise ValueError('Expected nonempty message_id, order_id and a known event_type')


def rebuild(events: list[dict]) -> str:
    """The stored event stream, not a mutable row, determines the state."""
    state = 'NOT_CREATED'
    for event in events:
        if event['eventType'] == 'OrderCreated':
            state = 'CREATED'
        elif event['eventType'] == 'OrderApproved':
            state = 'APPROVED'
    return state
