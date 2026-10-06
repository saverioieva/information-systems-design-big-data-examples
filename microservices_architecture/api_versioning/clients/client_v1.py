#!/usr/bin/env python3
import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def fetch(url: str) -> tuple[dict, str | None]:
    request = Request(url, headers={"Accept": "application/json"})
    with urlopen(request, timeout=5) as response:
        payload = json.load(response)
        return payload, response.headers.get("X-API-Version")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="A v1 client that understands only id, status, and total."
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8083/v1/orders/123",
        help="Order endpoint to call",
    )
    args = parser.parse_args()

    try:
        payload, api_version = fetch(args.url)
    except (HTTPError, URLError) as exc:
        print(f"Request failed: {exc}")
        return 1

    required = {"id", "status", "total"}
    missing = required - payload.keys()
    if missing:
        print("INCOMPATIBLE with the v1 client")
        print("Missing expected fields:", ", ".join(sorted(missing)))
        print("Received:", json.dumps(payload, indent=2))
        return 2

    known = {key: payload[key] for key in ("id", "status", "total")}
    extras = sorted(set(payload) - required)

    print(f"API version: {api_version or 'unknown'}")
    print("v1 client successfully read:")
    print(json.dumps(known, indent=2))
    if extras:
        print("Ignored additional fields:", ", ".join(extras))
    return 0


if __name__ == "__main__":
    sys.exit(main())
