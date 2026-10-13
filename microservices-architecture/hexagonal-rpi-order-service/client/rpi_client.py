import os

import requests


BASE_URL = os.getenv("ORDER_API_BASE_URL", "http://localhost:8000")


def main() -> None:
    created = requests.post(
        f"{BASE_URL}/orders",
        json={"restaurantId": 42, "total": 25.50},
        timeout=5,
    )
    created.raise_for_status()
    order = created.json()
    print("Created:", order)

    fetched = requests.get(
        f"{BASE_URL}/orders/{order['id']}",
        timeout=5,
    )
    fetched.raise_for_status()
    print("Fetched:", fetched.json())


if __name__ == "__main__":
    main()
