import argparse
import importlib

COHESION = [
    "functional",
    "sequential",
    "communicational",
    "procedural",
    "temporal",
    "logical",
    "coincidental",
]

COUPLING = [
    "no_coupling",
    "message_coupling",
    "data_coupling",
    "stamp_coupling",
    "control_coupling",
    "external_coupling",
    "common_coupling",
    "content_coupling",
]


def title(name: str) -> str:
    return name.replace("_", " ").title()


def run_example(group: str, name: str) -> None:
    module = importlib.import_module(f"{group}.{name}")
    print(f"\n=== {title(name)} ===")
    for line in module.demo():
        print(line)


def run_group(group: str, names: list[str]) -> None:
    for name in names:
        run_example(group, name)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Teaching examples for cohesion and coupling levels."
    )
    parser.add_argument(
        "group",
        choices=["all", "cohesion", "coupling"],
        nargs="?",
        default="all",
    )
    parser.add_argument(
        "level",
        nargs="?",
        help="Optional example name, such as sequential, stamp, or content.",
    )
    args = parser.parse_args()

    if args.group == "all":
        if args.level:
            parser.error("a level can be used only with cohesion or coupling")
        print("######## COHESION ########")
        run_group("cohesion", COHESION)
        print("\n######## COUPLING ########")
        run_group("coupling", COUPLING)
        return

    names = COHESION if args.group == "cohesion" else COUPLING
    if args.level:
        normalized = args.level.replace("-", "_")
        aliases = {
            "function": "functional",
            "communication": "communicational",
            "no": "no_coupling",
            "message": "message_coupling",
            "data": "data_coupling",
            "stamp": "stamp_coupling",
            "control": "control_coupling",
            "external": "external_coupling",
            "common": "common_coupling",
            "content": "content_coupling",
        }
        normalized = aliases.get(normalized, normalized)
        if normalized not in names:
            parser.error(
                f"unknown {args.group} level '{args.level}'. "
                f"Choose from: {', '.join(names)}"
            )
        run_example(args.group, normalized)
        return

    run_group(args.group, names)


if __name__ == "__main__":
    main()
