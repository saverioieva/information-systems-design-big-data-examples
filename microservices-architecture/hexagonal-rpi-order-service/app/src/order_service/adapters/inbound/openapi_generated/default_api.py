from decimal import Decimal

from fastapi import HTTPException

# This base class is created by `make generate-server-skeleton`.
# Importing this module is therefore meaningful only in the generated-server
# runtime, where /generated/src is added to PYTHONPATH.
from openapi_server.apis.default_api_base import BaseDefaultApi

from order_service.bootstrap import build_order_use_cases
from order_service.domain.order import Order as DomainOrder


_use_cases = build_order_use_cases()


def _to_transport_dict(order: DomainOrder) -> dict[str, object]:
    assert order.id is not None
    return {
        "id": order.id,
        "restaurantId": order.restaurant_id,
        "status": order.status,
        "total": float(order.total),
    }


class DefaultApiImpl(BaseDefaultApi):
    """Handwritten inbound adapter for the OpenAPI-generated transport layer.

    OpenAPI Generator owns the route declarations and transport DTOs. This
    class is registered as a BaseDefaultApi implementation and delegates each
    generated operation to the framework-independent OrderUseCases port.
    """

    async def create_order(self, create_order_request):
        # Use aliases so this adapter depends on the published contract names,
        # not on the generated Pydantic model's internal Python field names.
        payload = create_order_request.model_dump(by_alias=True)
        try:
            order = _use_cases.create_order(
                int(payload["restaurantId"]),
                Decimal(str(payload["total"])),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _to_transport_dict(order)

    async def get_order(self, order_id: int):
        order = _use_cases.get_order(order_id)
        if order is None:
            raise HTTPException(status_code=404, detail="Order not found")
        return _to_transport_dict(order)
