"""Data coupling: modules communicate by passing only the simple data required."""


class PricingModule:
    def total(self, unit_price: float, quantity: int) -> float:
        return unit_price * quantity


class OrderModule:
    def __init__(self, pricing: PricingModule):
        self.pricing = pricing

    def order_total(self) -> float:
        # Only the required primitive values cross the module boundary.
        return self.pricing.total(unit_price=12.0, quantity=2)


def demo() -> list[str]:
    total = OrderModule(PricingModule()).order_total()
    return [
        f"total=EUR {total:.2f}",
        "Observe: Module A passes only the values Module B needs.",
    ]
