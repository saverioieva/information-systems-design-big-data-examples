import json
import time
import urllib.error
import urllib.request

BASE_URL = "http://order-generated:8000"


def request(method: str, path: str, payload: dict | None = None) -> tuple[int, str]:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    with urllib.request.urlopen(req, timeout=3) as response:
        return response.status, response.read().decode("utf-8")


print(f"Waiting for generated OpenAPI server at {BASE_URL}...")
for _ in range(30):
    try:
        status, _ = request("GET", "/openapi.json")
        if status == 200:
            break
    except (urllib.error.URLError, TimeoutError):
        time.sleep(1)
else:
    raise SystemExit("Generated server did not become ready.")

print("\nPOST /orders through generated skeleton")
status, body = request(
    "POST",
    "/orders",
    {"restaurantId": 42, "total": 25.50},
)
print(f"HTTP {status}")
print(body)
created = json.loads(body)
order_id = created["id"]

print(f"\nGET /orders/{order_id} through generated skeleton")
status, body = request("GET", f"/orders/{order_id}")
print(f"HTTP {status}")
print(body)
