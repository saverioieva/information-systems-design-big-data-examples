"""Content coupling: one module directly accesses another module's internal state."""


class OrderModule:
    def __init__(self, total_cents: int):
        self._total_cents = total_cents

    def total_cents(self) -> int:
        return self._total_cents


class DiscountModule:
    def apply_bad_discount(self, order: OrderModule) -> None:
        # Pathological coupling: directly modify another module's internal data.
        order._total_cents -= 500


def demo() -> list[str]:
    order = OrderModule(2_000)
    before = order.total_cents()
    DiscountModule().apply_bad_discount(order)
    after = order.total_cents()
    return [
        f"before direct internal change: {before} cents",
        f"after direct internal change:  {after} cents",
        "Observe: DiscountModule reaches inside OrderModule and changes its private state.",
    ]
