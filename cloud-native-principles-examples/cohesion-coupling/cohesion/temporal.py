"""Temporal cohesion: tasks are grouped because they happen at the same time."""


def load_configuration() -> str:
    return "configuration loaded"


def connect_logger() -> str:
    return "logger connected"


def warm_cache() -> str:
    return "cache warmed"


def startup() -> list[str]:
    # These tasks are different; they are grouped because they all run at startup.
    return [load_configuration(), connect_logger(), warm_cache()]


def demo() -> list[str]:
    return [
        *startup(),
        "Observe: unrelated startup tasks are grouped by execution time.",
    ]
