import json
import os
import time
from urllib.request import Request, urlopen


REQUEST_COUNT = int(os.getenv("REQUEST_COUNT", "50"))
PAYLOAD = json.dumps({"sku": "pizza", "quantity": 2}).encode("utf-8")
TARGETS = (
    ("gRPC internal", "http://checkout-grpc:8000/checkouts"),
    ("REST internal", "http://checkout-rest:8000/checkouts"),
)


def invoke(url: str) -> None:
    request = Request(
        url,
        data=PAYLOAD,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=5) as response:
        response.read()


for label, url in TARGETS:
    started = time.perf_counter()
    for _ in range(REQUEST_COUNT):
        invoke(url)
    elapsed = time.perf_counter() - started
    print(f"{label}: {REQUEST_COUNT} checkout requests in {elapsed:.4f}s")

print("Open http://localhost:9090 to compare the Prometheus metrics by protocol.")
