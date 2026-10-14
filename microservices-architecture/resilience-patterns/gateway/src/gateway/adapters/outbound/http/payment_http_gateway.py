from gateway.application.ports.outbound.payment_gateway import PaymentGateway
from gateway.domain.models import Payment
from gateway.infrastructure.resilience.resilient_http_client import ResilientHttpClient


class PaymentHttpGateway(PaymentGateway):
    def __init__(self, client: ResilientHttpClient) -> None:
        self._client = client

    async def get_payment(self, order_id: str) -> Payment:
        data = await self._client.get_json(f"/payments/{order_id}")
        return Payment(
            order_id=data["orderId"],
            payment_id=data["paymentId"],
            amount=float(data["amount"]),
            currency=data["currency"],
            method=data["method"],
            status=data["status"],
        )
