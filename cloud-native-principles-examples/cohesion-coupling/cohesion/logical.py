"""Logical cohesion: similar categories of operations are grouped together."""


def handle_document(action: str, document: str) -> str:
    # One generic entry point selects among logically related operations.
    if action == "print":
        return f"printing {document}"
    if action == "save":
        return f"saving {document}"
    if action == "delete":
        return f"deleting {document}"
    raise ValueError(f"unknown action: {action}")


def demo() -> list[str]:
    return [
        handle_document("print", "report.pdf"),
        handle_document("save", "report.pdf"),
        "Observe: operations are grouped because they are the same general kind of utility.",
    ]
