"""Stamp coupling: a whole structure is passed although only part is required."""

from dataclasses import dataclass


@dataclass
class Customer:
    customer_id: int
    name: str
    email: str
    address: str


class ShippingModule:
    def destination(self, customer: Customer) -> str:
        # This module receives the whole Customer but needs only one field.
        return customer.address


class OrderModule:
    def __init__(self, shipping: ShippingModule):
        self.shipping = shipping

    def shipping_destination(self, customer: Customer) -> str:
        return self.shipping.destination(customer)


def demo() -> list[str]:
    customer = Customer(7, "Alice", "alice@example.com", "Via Roma 10")
    destination = OrderModule(ShippingModule()).shipping_destination(customer)
    return [
        f"destination={destination}",
        "Observe: ShippingModule receives an entire Customer object but uses only address.",
    ]
