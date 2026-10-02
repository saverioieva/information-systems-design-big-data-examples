import argparse
import sys

import requests

BASE_URL = "http://localhost:8080"

EXPECTED_FIELDS = {
    "mobile": {"name", "policy_status", "next_payment_eur"},
    "support": {"customer_id", "name", "email", "policy_id", "policy_status"},
}

PATHS = {
    "mobile": "/consumer-first/mobile/customers/42",
    "support": "/consumer-first/support/customers/42",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("consumer", choices=sorted(PATHS))
    args = parser.parse_args()

    response = requests.get(BASE_URL + PATHS[args.consumer], timeout=3)
    response.raise_for_status()
    payload = response.json()

    actual = set(payload)
    expected = EXPECTED_FIELDS[args.consumer]

    print(f"Consumer: {args.consumer}")
    print(f"Response: {payload}")
    print(f"Expected fields: {sorted(expected)}")

    if actual != expected:
        print(f"FAIL: unexpected contract fields: {sorted(actual)}", file=sys.stderr)
        return 1

    print("PASS: the response contains exactly the data this consumer needs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
