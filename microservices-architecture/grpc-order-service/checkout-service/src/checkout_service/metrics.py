from prometheus_client import Counter, Histogram


INVENTORY_CLIENT_REQUESTS = Counter(
    "inventory_client_requests_total",
    "Inventory calls performed by Checkout.",
    ["protocol", "status"],
)

INVENTORY_CLIENT_DURATION = Histogram(
    "inventory_client_duration_seconds",
    "Checkout-observed latency of the Inventory call.",
    ["protocol"],
    buckets=(
        0.0001,
        0.00025,
        0.0005,
        0.001,
        0.0025,
        0.005,
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1.0,
        2.5,
    ),
)

INVENTORY_CLIENT_REQUEST_BYTES = Histogram(
    "inventory_client_request_payload_bytes",
    "Serialized application payload size sent to Inventory, excluding transport headers/framing.",
    ["protocol"],
    buckets=(1, 5, 10, 20, 50, 100, 200, 500, 1000, 5000),
)

INVENTORY_CLIENT_RESPONSE_BYTES = Histogram(
    "inventory_client_response_payload_bytes",
    "Serialized application payload size received from Inventory, excluding transport headers/framing.",
    ["protocol"],
    buckets=(1, 5, 10, 20, 50, 100, 200, 500, 1000, 5000),
)
