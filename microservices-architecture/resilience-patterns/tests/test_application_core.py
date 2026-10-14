import asyncio
import unittest

from gateway.application.ports.outbound.delivery_gateway import DeliveryGateway
from gateway.application.ports.outbound.errors import TransientCallError
from gateway.application.ports.outbound.kitchen_gateway import KitchenGateway
from gateway.application.ports.outbound.order_gateway import OrderGateway
from gateway.application.ports.outbound.payment_cache import PaymentCache
from gateway.application.ports.outbound.payment_gateway import PaymentGateway
from gateway.application.services.order_composition_service import OrderCompositionService
from gateway.domain.models import Delivery, KitchenTicket, Order, Payment


class FakeOrderGateway(OrderGateway):
    async def get_order(self, order_id: str) -> Order:
        return Order(order_id, [{"sku": "PIZZA", "qty": 1}], "CONFIRMED")


class FakeKitchenGateway(KitchenGateway):
    def __init__(self, fail=False):
        self.fail = fail

    async def get_ticket(self, order_id: str) -> KitchenTicket:
        if self.fail:
            raise TransientCallError("kitchen down")
        return KitchenTicket(order_id, "K-1", "IN_PREP", "PIZZA")


class FakeDeliveryGateway(DeliveryGateway):
    async def get_delivery(self, order_id: str) -> Delivery:
        return Delivery(order_id, "D-1", 25, "PICKED_UP")


class FakePaymentGateway(PaymentGateway):
    def __init__(self, fail=False):
        self.fail = fail

    async def get_payment(self, order_id: str) -> Payment:
        if self.fail:
            raise TransientCallError("payment down")
        return Payment(order_id, "P-1", 21.5, "EUR", "CARD", "PAID")


class FakePaymentCache(PaymentCache):
    def __init__(self):
        self.value = None

    def get(self, order_id: str):
        return self.value if self.value and self.value.order_id == order_id else None

    def put(self, payment: Payment):
        self.value = payment


class ApplicationCoreTests(unittest.TestCase):
    def test_optional_failure_degrades_without_fastapi_or_http(self):
        cache = FakePaymentCache()
        service = OrderCompositionService(
            FakeOrderGateway(),
            FakeKitchenGateway(fail=True),
            FakeDeliveryGateway(),
            FakePaymentGateway(),
            cache,
        )
        result = asyncio.run(service.compose_order("1001"))
        self.assertTrue(result.degraded)
        self.assertIsNone(result.kitchen)
        self.assertEqual(["kitchen"], result.missing)

    def test_payment_cache_fallback_is_application_policy(self):
        cache = FakePaymentCache()
        healthy = OrderCompositionService(
            FakeOrderGateway(), FakeKitchenGateway(), FakeDeliveryGateway(), FakePaymentGateway(), cache
        )
        asyncio.run(healthy.compose_order("1001"))

        degraded = OrderCompositionService(
            FakeOrderGateway(), FakeKitchenGateway(), FakeDeliveryGateway(), FakePaymentGateway(fail=True), cache
        )
        result = asyncio.run(degraded.compose_order("1001"))
        self.assertEqual("cache", result.payment.source)
        self.assertEqual(["payment-cache"], result.fallbacks)


if __name__ == "__main__":
    unittest.main()
