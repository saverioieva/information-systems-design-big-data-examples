"""Coincidental cohesion: unrelated operations happen to be grouped together."""


def send_email(address: str) -> str:
    return f"email sent to {address}"


def calculate_tax(amount: float) -> float:
    return amount * 0.22


def format_date(day: int, month: int, year: int) -> str:
    return f"{day:02d}/{month:02d}/{year}"


def demo() -> list[str]:
    return [
        send_email("student@example.com"),
        f"tax={calculate_tax(100.0):.2f}",
        f"date={format_date(2, 10, 2026)}",
        "Observe: the functions have no meaningful shared purpose or data.",
    ]
