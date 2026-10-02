"""Functional cohesion: every element contributes to one focused task."""


def calculate_interest(principal: float, rate: float) -> float:
    """One function, one well-defined responsibility."""
    return principal * rate


def demo() -> list[str]:
    interest = calculate_interest(1_000.0, 0.05)
    return [
        "Task: calculate interest",
        f"Result: EUR {interest:.2f}",
        "Observe: all code contributes to the same calculation.",
    ]
