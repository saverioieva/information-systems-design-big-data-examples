"""No coupling: two modules perform independent work and never communicate."""


class GreetingModule:
    def message(self) -> str:
        return "Welcome"


class ClockModule:
    def format_hour(self, hour: int) -> str:
        return f"{hour:02d}:00"


def demo() -> list[str]:
    greeting = GreetingModule().message()
    time_text = ClockModule().format_hour(9)
    return [
        f"GreetingModule -> {greeting}",
        f"ClockModule -> {time_text}",
        "Observe: neither module knows about or communicates with the other.",
    ]
