from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Order:
    id: int | None
    restaurant_id: int
    status: str
    total: Decimal
