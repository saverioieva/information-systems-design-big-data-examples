from abc import ABC, abstractmethod

from checkout_service.domain.checkout import CheckoutResult


class CheckoutUseCases(ABC):
    """Inbound port exposed by the Checkout application core."""

    @abstractmethod
    def create_checkout(self, sku: str, quantity: int) -> CheckoutResult:
        raise NotImplementedError
