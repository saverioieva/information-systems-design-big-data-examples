from gateway.application.ports.outbound.order_gateway import OrderGateway
from gateway.domain.models import Order
from gateway.infrastructure.resilience.resilient_http_client import ResilientHttpClient


class OrderHttpGateway(OrderGateway):
    def __init__(self, client: ResilientHttpClient) -> None:
        self._client = client

    async def get_order(self, order_id: str) -> Order:
        data = await self._client.get_json(f"/orders/{order_id}")
        return Order(order_id=data["orderId"], items=data["items"], status=data["status"])
