import json
import time

import httpx

from checkout_service.application.ports.outbound.inventory_gateway import (
    InventoryAvailability,
    InventoryGateway,
)
from checkout_service.metrics import (
    INVENTORY_CLIENT_DURATION,
    INVENTORY_CLIENT_REQUEST_BYTES,
    INVENTORY_CLIENT_REQUESTS,
    INVENTORY_CLIENT_RESPONSE_BYTES,
)


class RestInventoryClient(InventoryGateway):
    """Outbound adapter: InventoryGateway -> Inventory HTTP/JSON endpoint."""

    protocol = "rest"

    def __init__(self, base_url: str) -> None:
        self._client = httpx.Client(base_url=base_url, timeout=3.0)

    def check_availability(self, sku: str, quantity: int) -> InventoryAvailability:
        # Serialize explicitly so the measured request size is the exact JSON body sent.
        request_body = json.dumps(
            {"sku": sku, "quantity": quantity}, separators=(",", ":")
        ).encode("utf-8")
        INVENTORY_CLIENT_REQUEST_BYTES.labels(protocol=self.protocol).observe(
            len(request_body)
        )

        started = time.perf_counter()
        try:
            response = self._client.post(
                "/availability",
                content=request_body,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            INVENTORY_CLIENT_REQUESTS.labels(protocol=self.protocol, status="error").inc()
            raise RuntimeError(f"inventory REST call failed: {exc}") from exc
        finally:
            INVENTORY_CLIENT_DURATION.labels(protocol=self.protocol).observe(
                time.perf_counter() - started
            )

        INVENTORY_CLIENT_RESPONSE_BYTES.labels(protocol=self.protocol).observe(
            len(response.content)
        )
        INVENTORY_CLIENT_REQUESTS.labels(protocol=self.protocol, status="success").inc()

        data = response.json()
        return InventoryAvailability(
            sku=data["sku"],
            requested_quantity=data["requestedQuantity"],
            available_quantity=data["availableQuantity"],
            available=data["available"],
        )
