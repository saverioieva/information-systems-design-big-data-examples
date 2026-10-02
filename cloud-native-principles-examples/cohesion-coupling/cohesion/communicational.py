"""Communicational cohesion: operations are grouped around the same data."""


class CustomerRecord:
    def __init__(self, name: str, email: str):
        self.data = {"name": name, "email": email, "active": True}

    def validate(self) -> bool:
        return "@" in self.data["email"]

    def update_email(self, new_email: str) -> None:
        self.data["email"] = new_email

    def summary(self) -> str:
        return f"{self.data['name']} <{self.data['email']}>"


def demo() -> list[str]:
    customer = CustomerRecord("Alice", "alice@example.com")
    before = customer.validate()
    customer.update_email("alice@new.example")
    return [
        f"Valid before update: {before}",
        f"Customer: {customer.summary()}",
        "Observe: validate, update, and summary all operate on the same customer data.",
    ]
