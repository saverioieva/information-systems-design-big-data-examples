from __future__ import annotations

import os

from fastapi import FastAPI

from gateway.adapters.inbound.rest.routes import build_business_router, build_diagnostics_router
from gateway.adapters.outbound.cache.in_memory_payment_cache import InMemoryPaymentCache
from gateway.adapters.outbound.http.delivery_http_gateway import DeliveryHttpGateway
from gateway.adapters.outbound.http.kitchen_http_gateway import KitchenHttpGateway
from gateway.adapters.outbound.http.order_http_gateway import OrderHttpGateway
from gateway.adapters.outbound.http.payment_http_gateway import PaymentHttpGateway
from gateway.application.services.order_composition_service import OrderCompositionService
from gateway.infrastructure.resilience.resilient_http_client import ResilientHttpClient


def build_resilient_client(name: str, base_url: str) -> ResilientHttpClient:
    return ResilientHttpClient(
        name,
        base_url,
        timeout_s=float(os.getenv("DOWNSTREAM_TIMEOUT_S", "0.8")),
        max_attempts=int(os.getenv("RETRY_MAX_ATTEMPTS", "3")),
        initial_backoff_s=float(os.getenv("RETRY_INITIAL_BACKOFF_S", "0.2")),
        max_backoff_s=float(os.getenv("RETRY_MAX_BACKOFF_S", "1.5")),
        failure_threshold=int(os.getenv("CIRCUIT_FAILURE_THRESHOLD", "2")),
        recovery_timeout_s=float(os.getenv("CIRCUIT_RECOVERY_TIMEOUT_S", "5")),
        max_concurrency=int(os.getenv("BULKHEAD_MAX_CONCURRENCY", "2")),
        max_queue=int(os.getenv("BULKHEAD_MAX_QUEUE", "2")),
    )


ORDER_URL = os.getenv("ORDER_SERVICE_URL", "http://order-service:8001")
KITCHEN_URL = os.getenv("KITCHEN_SERVICE_URL", "http://kitchen-service:8002")
DELIVERY_URL = os.getenv("DELIVERY_SERVICE_URL", "http://delivery-service:8003")
PAYMENT_URL = os.getenv("PAYMENT_SERVICE_URL", "http://payment-service:8004")

resilient_clients = {
    "order": build_resilient_client("order", ORDER_URL),
    "kitchen": build_resilient_client("kitchen", KITCHEN_URL),
    "delivery": build_resilient_client("delivery", DELIVERY_URL),
    "payment": build_resilient_client("payment", PAYMENT_URL),
}

order_gateway = OrderHttpGateway(resilient_clients["order"])
kitchen_gateway = KitchenHttpGateway(resilient_clients["kitchen"])
delivery_gateway = DeliveryHttpGateway(resilient_clients["delivery"])
payment_gateway = PaymentHttpGateway(resilient_clients["payment"])
payment_cache = InMemoryPaymentCache()

application = OrderCompositionService(
    order_gateway=order_gateway,
    kitchen_gateway=kitchen_gateway,
    delivery_gateway=delivery_gateway,
    payment_gateway=payment_gateway,
    payment_cache=payment_cache,
)

app = FastAPI(title="Resilient API Composition Gateway")
app.include_router(build_business_router(application, application))
app.include_router(
    build_diagnostics_router(
        lambda: {name: client.snapshot() for name, client in resilient_clients.items()}
    )
)
