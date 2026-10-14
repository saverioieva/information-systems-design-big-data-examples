from gateway.application.ports.outbound.delivery_gateway import DeliveryGateway
from gateway.domain.models import Delivery
from gateway.infrastructure.resilience.resilient_http_client import ResilientHttpClient


class DeliveryHttpGateway(DeliveryGateway):
    def __init__(self, client: ResilientHttpClient) -> None:
        self._client = client

    async def get_delivery(self, order_id: str) -> Delivery:
        data = await self._client.get_json(f"/deliveries/{order_id}")
        return Delivery(
            order_id=data["orderId"],
            delivery_id=data["deliveryId"],
            eta_minutes=data["etaMinutes"],
            status=data["status"],
        )
