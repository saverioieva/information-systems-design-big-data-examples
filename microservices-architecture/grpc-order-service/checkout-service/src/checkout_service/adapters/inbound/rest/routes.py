from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from checkout_service.application.ports.inbound.checkout_use_cases import CheckoutUseCases


class CreateCheckoutBody(BaseModel):
    sku: str = Field(min_length=1)
    quantity: int = Field(gt=0)


def create_router(use_cases: CheckoutUseCases) -> APIRouter:
    """Inbound REST adapter: HTTP/JSON -> CheckoutUseCases."""

    router = APIRouter()

    @router.get("/health")
    def health():
        return {"status": "ok"}

    @router.post("/checkouts", status_code=201)
    def create_checkout(body: CreateCheckoutBody):
        try:
            result = use_cases.create_checkout(body.sku, body.quantity)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        return {
            "sku": result.sku,
            "quantity": result.quantity,
            "availableQuantity": result.available_quantity,
            "status": result.status.value,
        }

    return router
