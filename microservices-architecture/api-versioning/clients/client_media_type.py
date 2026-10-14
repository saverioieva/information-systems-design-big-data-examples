#!/usr/bin/env python3
import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

MEDIA_TYPES = {
    1: "application/vnd.ftgo.order.v1+json",
    2: "application/vnd.ftgo.order.v2+json",
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Call the stable Order URI using Accept-based API versioning."
    )
    parser.add_argument("--version", type=int, choices=(1, 2), required=True)
    parser.add_argument(
        "--url",
        default="http://localhost:8083/orders/123",
        help="Stable Order resource URI",
    )
    args = parser.parse_args()

    media_type = MEDIA_TYPES[args.version]
    request = Request(args.url, headers={"Accept": media_type})

    try:
        with urlopen(request, timeout=5) as response:
            payload = json.load(response)
            print(f"Request Accept: {media_type}")
            print(f"Response Content-Type: {response.headers.get('Content-Type')}")
            print(f"API major version: {response.headers.get('X-API-Version')}")
            print(f"Service version: {response.headers.get('X-Service-Version')}")
            print(f"Vary: {response.headers.get('Vary')}")
            print(json.dumps(payload, indent=2))
    except (HTTPError, URLError) as exc:
        print(f"Request failed: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
