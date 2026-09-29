class CardPaymentService:
    def pay(self, amount):
        return f"Card payment completed: EUR {amount:.2f}"


class CheckoutService:
    def __init__(self):
        self.payment_service = CardPaymentService()

    def checkout(self, amount):
        return self.payment_service.pay(amount)


def demo():
    return CheckoutService().checkout(12.00)
