import os
import time

import requests

ROUTER_URL = os.getenv("ROUTER_URL", "http://nginx-router")
ORDER_ID = os.getenv("ORDER_ID", "1001")
REQUEST_COUNT = int(os.getenv("REQUEST_COUNT", "9"))


def wait_for_router() -> None:
    last_error = None
    for _ in range(40):
        try:
            response = requests.get(
                f"{ROUTER_URL}/orders/{ORDER_ID}",
                timeout=2,
            )
            if response.ok:
                return
        except requests.RequestException as exc:
            last_error = exc
        time.sleep(1)
    raise RuntimeError(f"Router did not become ready: {last_error}")


def main() -> None:
    wait_for_router()
    print("Platform-provided discovery demo")
    print(
        "Client calls one logical endpoint; Nginx resolves the service through "
        "Consul DNS and load balances across healthy instances.\n"
    )

    for request_number in range(1, REQUEST_COUNT + 1):
        response = requests.get(
            f"{ROUTER_URL}/orders/{ORDER_ID}",
            timeout=3,
        )
        response.raise_for_status()
        body = response.json()
        print(
            f"{request_number:02d}. HTTP {response.status_code} -> "
            f"served by {body['instance']}"
        )
        time.sleep(0.3)


if __name__ == "__main__":
    main()
