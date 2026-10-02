"""Procedural cohesion: operations are grouped because they follow one control flow."""


def check_permissions() -> str:
    return "permissions checked"


def open_file() -> str:
    return "file opened"


def process_file() -> str:
    return "file processed"


def close_file() -> str:
    return "file closed"


def handle_file() -> list[str]:
    # The operations are connected mainly by their required execution order.
    return [
        check_permissions(),
        open_file(),
        process_file(),
        close_file(),
    ]


def demo() -> list[str]:
    return [
        *handle_file(),
        "Observe: the steps belong together mainly because of the procedure/order.",
    ]
