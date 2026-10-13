import json
from urllib.request import Request, urlopen

payload = json.dumps({"sku": "pizza", "quantity": 2}).encode()
request = Request(
    "http://localhost:8000/checkouts",
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urlopen(request) as response:
    print(response.read().decode())
