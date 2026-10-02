"""Sequential cohesion: output from one step becomes input to the next."""


def extract(raw: str) -> list[str]:
    return raw.split(",")


def transform(values: list[str]) -> list[int]:
    return [int(value.strip()) * 2 for value in values]


def load(values: list[int]) -> str:
    return f"stored={values}"


def run_pipeline(raw: str) -> str:
    extracted = extract(raw)
    transformed = transform(extracted)
    return load(transformed)


def demo() -> list[str]:
    return [
        "Pipeline: extract -> transform -> load",
        f"Result: {run_pipeline('2, 4, 6')}",
        "Observe: each step consumes the previous step's output.",
    ]
