#!/usr/bin/env python3
import argparse
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main() -> int:
    parser = argparse.ArgumentParser(description="A client for the FTGO Order API v2 contract.")
    parser.add_argument(
        "--url",
        default="http://localhost:8083/v2/orders/123",
        help="Order endpoint to call",
    )
    args = parser.parse_args()

    try:
        request = Request(args.url, headers={"Accept": "application/json"})
        with urlopen(request, timeout=5) as response:
            payload = json.load(response)
            api_version = response.headers.get("X-API-Version")
    except (HTTPError, URLError) as exc:
        print(f"Request failed: {exc}")
        return 1

    total = payload["totalAmount"]
    print(f"API version: {api_version or 'unknown'}")
    print(
        f"Order {payload['id']}: {payload['orderStatus']} - "
        f"{total['value']:.2f} {total['currency']}"
    )
    print(f"Delivery ETA: {payload['delivery']['eta']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
