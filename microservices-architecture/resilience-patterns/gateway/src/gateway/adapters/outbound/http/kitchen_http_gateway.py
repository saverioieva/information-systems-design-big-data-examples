from gateway.application.ports.outbound.kitchen_gateway import KitchenGateway
from gateway.domain.models import KitchenTicket
from gateway.infrastructure.resilience.resilient_http_client import ResilientHttpClient


class KitchenHttpGateway(KitchenGateway):
    def __init__(self, client: ResilientHttpClient) -> None:
        self._client = client

    async def get_ticket(self, order_id: str) -> KitchenTicket:
        data = await self._client.get_json(f"/tickets/{order_id}")
        return KitchenTicket(
            order_id=data["orderId"],
            ticket_id=data["ticketId"],
            status=data["status"],
            station=data["station"],
        )
