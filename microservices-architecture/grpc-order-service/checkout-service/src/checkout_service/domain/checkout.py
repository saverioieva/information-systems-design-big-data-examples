from dataclasses import dataclass
from enum import Enum


class CheckoutStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class CheckoutResult:
    sku: str
    quantity: int
    available_quantity: int
    status: CheckoutStatus
