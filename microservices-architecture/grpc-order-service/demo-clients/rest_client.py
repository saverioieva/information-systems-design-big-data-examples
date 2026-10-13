import json
import os
from urllib.request import Request, urlopen

checkout_url = os.getenv("CHECKOUT_URL", "http://checkout-grpc:8000/checkouts")
payload = json.dumps({"sku": "pizza", "quantity": 2}).encode()
request = Request(
    checkout_url,
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urlopen(request) as response:
    print(response.read().decode())
