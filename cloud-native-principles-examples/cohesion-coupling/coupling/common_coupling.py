"""Common coupling: multiple modules depend on shared global data."""


GLOBAL_CONFIG = {
    "currency": "EUR",
    "tax_rate": 0.22,
}


class BillingModule:
    def total_with_tax(self, amount: float) -> float:
        return amount * (1 + GLOBAL_CONFIG["tax_rate"])


class AdminModule:
    def change_tax_rate(self, new_rate: float) -> None:
        GLOBAL_CONFIG["tax_rate"] = new_rate


def demo() -> list[str]:
    before = BillingModule().total_with_tax(100.0)
    AdminModule().change_tax_rate(0.25)
    after = BillingModule().total_with_tax(100.0)
    return [
        f"before global change: EUR {before:.2f}",
        f"after global change:  EUR {after:.2f}",
        "Observe: changing shared global data changes another module's behavior.",
    ]
