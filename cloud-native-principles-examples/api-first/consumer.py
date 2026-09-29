import json
import os
import urllib.request


def validate(data):
    assert type(data.get("id")) is int, "id must be integer"
    assert isinstance(data.get("name"), str), "name must be string"
    assert type(data.get("price_cents")) is int, "price_cents missing or changed"
    assert data["price_cents"] >= 0


if __name__ == "__main__":
    url = os.getenv("API_URL", "http://localhost:5000") + "/products/1"
    with urllib.request.urlopen(url, timeout=2) as response:
        data = json.load(response)

    validate(data)
    print(f"PASS: {data['name']} costs {data['price_cents']} cents")
