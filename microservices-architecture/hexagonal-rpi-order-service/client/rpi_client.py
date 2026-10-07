"""Small synchronous RPI client adapter used for the lab."""

import requests

BASE_URL = "http://localhost:8000"


def main() -> None:
    created = requests.post(
        f"{BASE_URL}/orders",
        json={"restaurantId": 42, "total": 25.50},
        timeout=3,
    )
    created.raise_for_status()
    order = created.json()
    print("POST /orders ->", order)

    fetched = requests.get(
        f"{BASE_URL}/orders/{order['id']}",
        timeout=3,
    )
    fetched.raise_for_status()
    print("GET /orders/{id} ->", fetched.json())


if __name__ == "__main__":
    main()
