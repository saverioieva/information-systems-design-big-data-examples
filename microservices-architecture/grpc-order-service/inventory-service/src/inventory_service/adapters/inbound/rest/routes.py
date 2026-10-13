from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from inventory_service.application.ports.inbound.inventory_use_cases import InventoryUseCases


class CheckAvailabilityBody(BaseModel):
    sku: str = Field(min_length=1)
    quantity: int = Field(gt=0)


def create_router(use_cases: InventoryUseCases) -> APIRouter:
    """Inbound REST adapter: HTTP/JSON -> InventoryUseCases."""

    router = APIRouter()

    @router.get("/health")
    def health():
        return {"status": "ok"}

    @router.post("/availability")
    def check_availability(body: CheckAvailabilityBody):
        try:
            result = use_cases.check_availability(body.sku, body.quantity)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return {
            "sku": result.sku,
            "requestedQuantity": result.requested_quantity,
            "availableQuantity": result.available_quantity,
            "available": result.available,
        }

    return router
