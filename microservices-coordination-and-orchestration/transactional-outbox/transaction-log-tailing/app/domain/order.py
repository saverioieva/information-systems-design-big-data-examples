"""Business record plus publication intention; NOT Event Sourcing."""
from dataclasses import dataclass
from uuid import uuid4

@dataclass(frozen=True)
class OrderCreated:
    order_id: str
    event_id: str
    amount: float
    def as_message(self) -> dict:
        return {"eventId":self.event_id,"type":"OrderCreated","orderId":self.order_id,"amount":self.amount}

def new_order(amount: float) -> OrderCreated:
    if amount <= 0: raise ValueError('amount must be positive')
    return OrderCreated(str(uuid4()),str(uuid4()),amount)
