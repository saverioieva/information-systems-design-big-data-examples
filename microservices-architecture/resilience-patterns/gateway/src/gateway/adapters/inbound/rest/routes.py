from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, HTTPException

from gateway.adapters.inbound.rest.dto import model_to_dict, order_view_to_dict
from gateway.application.ports.inbound.dependency_probe_use_cases import DependencyProbeUseCases
from gateway.application.ports.inbound.order_composition_use_cases import OrderCompositionUseCases
from gateway.application.ports.outbound.errors import (
    BulkheadRejectedError,
    CircuitOpenError,
    DependencyUnavailableError,
    ResourceNotFoundError,
)
from gateway.application.services.order_composition_service import (
    OrderNotFound,
    RequiredDependencyUnavailable,
    UnknownDependency,
)


def build_business_router(
    order_use_cases: OrderCompositionUseCases,
    probe_use_cases: DependencyProbeUseCases,
) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @router.get("/orders/{order_id}")
    async def compose_order(order_id: str) -> dict:
        try:
            view = await order_use_cases.compose_order(order_id)
        except OrderNotFound as exc:
            raise HTTPException(status_code=404, detail="Order not found") from exc
        except RequiredDependencyUnavailable as exc:
            raise HTTPException(status_code=503, detail=f"Order service unavailable: {exc}") from exc
        return order_view_to_dict(view)

    @router.get("/diagnostics/dependencies/{service}/{order_id}")
    async def diagnose_dependency(service: str, order_id: str) -> dict:
        try:
            result = await probe_use_cases.probe_dependency(service, order_id)
        except UnknownDependency as exc:
            raise HTTPException(status_code=404, detail="Unknown downstream service") from exc
        except ResourceNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"{service} resource not found") from exc
        except BulkheadRejectedError as exc:
            raise HTTPException(status_code=429, detail=f"{service} bulkhead full") from exc
        except CircuitOpenError as exc:
            raise HTTPException(status_code=503, detail=f"{service} circuit is open") from exc
        except DependencyUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return model_to_dict(result)

    return router


def build_diagnostics_router(snapshot: Callable[[], dict]) -> APIRouter:
    router = APIRouter()

    @router.get("/resilience")
    async def resilience_status() -> dict:
        return snapshot()

    return router
