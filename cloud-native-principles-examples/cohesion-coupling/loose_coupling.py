class CardPaymentService:
    def pay(self, amount):
        return f"Card payment completed: EUR {amount:.2f}"


class CashPaymentService:
    def pay(self, amount):
        return f"Cash payment completed: EUR {amount:.2f}"


class CheckoutService:
    def __init__(self, payment_service):
        self.payment_service = payment_service

    def checkout(self, amount):
        return self.payment_service.pay(amount)


def demo():
    card_checkout = CheckoutService(CardPaymentService())
    cash_checkout = CheckoutService(CashPaymentService())
    return [
        card_checkout.checkout(12.00),
        cash_checkout.checkout(12.00),
    ]
