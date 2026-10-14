from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import Any, Awaitable

from gateway.application.ports.inbound.dependency_probe_use_cases import DependencyProbeUseCases
from gateway.application.ports.inbound.order_composition_use_cases import OrderCompositionUseCases
from gateway.application.ports.outbound.delivery_gateway import DeliveryGateway
from gateway.application.ports.outbound.errors import (
    DependencyUnavailableError,
    ResourceNotFoundError,
)
from gateway.application.ports.outbound.kitchen_gateway import KitchenGateway
from gateway.application.ports.outbound.order_gateway import OrderGateway
from gateway.application.ports.outbound.payment_cache import PaymentCache
from gateway.application.ports.outbound.payment_gateway import PaymentGateway
from gateway.domain.models import OrderView, Payment


class RequiredDependencyUnavailable(Exception):
    """Raised when the required Order dependency cannot serve the request."""


class OrderNotFound(Exception):
    """Raised when the required order does not exist."""


class UnknownDependency(Exception):
    """Raised by the teaching-only probe use case for an unknown service name."""


class OrderCompositionService(OrderCompositionUseCases, DependencyProbeUseCases):
    """Application core: orchestration and degradation policy only.

    This class has no dependency on FastAPI, HTTP, requests, PyBreaker,
    Tenacity, or thread pools. Those concerns live behind outbound ports.
    """

    def __init__(
        self,
        order_gateway: OrderGateway,
        kitchen_gateway: KitchenGateway,
        delivery_gateway: DeliveryGateway,
        payment_gateway: PaymentGateway,
        payment_cache: PaymentCache,
    ) -> None:
        self._order_gateway = order_gateway
        self._kitchen_gateway = kitchen_gateway
        self._delivery_gateway = delivery_gateway
        self._payment_gateway = payment_gateway
        self._payment_cache = payment_cache

    async def compose_order(self, order_id: str) -> OrderView:
        calls: dict[str, Awaitable[Any]] = {
            "order": self._order_gateway.get_order(order_id),
            "kitchen": self._kitchen_gateway.get_ticket(order_id),
            "delivery": self._delivery_gateway.get_delivery(order_id),
            "payment": self._payment_gateway.get_payment(order_id),
        }
        names = list(calls.keys())
        values = await asyncio.gather(*calls.values(), return_exceptions=True)
        results = dict(zip(names, values))

        order_result = results["order"]
        if isinstance(order_result, ResourceNotFoundError):
            raise OrderNotFound(order_id)
        if isinstance(order_result, Exception):
            raise RequiredDependencyUnavailable(str(order_result))

        missing: list[str] = []
        fallbacks: list[str] = []

        kitchen = self._optional_value("kitchen", results["kitchen"], missing)
        delivery = self._optional_value("delivery", results["delivery"], missing)
        payment = self._resolve_payment(order_id, results["payment"], missing, fallbacks)

        return OrderView(
            order=order_result,
            kitchen=kitchen,
            delivery=delivery,
            payment=payment,
            degraded=bool(missing or fallbacks),
            missing=missing,
            fallbacks=fallbacks,
        )

    async def probe_dependency(self, service: str, order_id: str) -> Any:
        probes = {
            "order": self._order_gateway.get_order,
            "kitchen": self._kitchen_gateway.get_ticket,
            "delivery": self._delivery_gateway.get_delivery,
            "payment": self._payment_gateway.get_payment,
        }
        try:
            probe = probes[service]
        except KeyError as exc:
            raise UnknownDependency(service) from exc
        return await probe(order_id)

    @staticmethod
    def _optional_value(name: str, value: Any, missing: list[str]) -> Any:
        if isinstance(value, ResourceNotFoundError):
            return None
        if isinstance(value, DependencyUnavailableError):
            missing.append(name)
            return None
        if isinstance(value, Exception):
            missing.append(name)
            return None
        return value

    def _resolve_payment(
        self,
        order_id: str,
        value: Any,
        missing: list[str],
        fallbacks: list[str],
    ) -> Payment | None:
        if isinstance(value, Payment):
            self._payment_cache.put(value)
            return value
        if isinstance(value, ResourceNotFoundError):
            return None

        cached = self._payment_cache.get(order_id)
        if cached is not None:
            fallbacks.append("payment-cache")
            return replace(cached, source="cache")

        missing.append("payment")
        return None
