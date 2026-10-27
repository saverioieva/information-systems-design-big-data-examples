"""Pure validation rules for the educational example (no network dependencies)."""


def validate(role: str, data: dict) -> bool:
    if role == "consumer":
        return data["consumer_id"].lower() != "blocked"
    if role == "restaurant":
        return data["item"].lower() != "unavailable"
    raise ValueError(f"Unexpected role: {role}")
