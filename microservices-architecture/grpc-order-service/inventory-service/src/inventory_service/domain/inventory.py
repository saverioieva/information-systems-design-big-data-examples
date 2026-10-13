from dataclasses import dataclass


@dataclass(frozen=True)
class InventoryItem:
    sku: str
    available_quantity: int


@dataclass(frozen=True)
class Availability:
    sku: str
    requested_quantity: int
    available_quantity: int
    available: bool


@dataclass(frozen=True)
class InventoryActionResult:
    sku: str
    message: str
    available_quantity: int
