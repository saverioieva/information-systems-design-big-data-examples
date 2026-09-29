class OrderService:
    def create_order(self, product, quantity):
        return {"product": product, "quantity": quantity}


class PaymentService:
    def pay(self, amount):
        return f"Payment completed: EUR {amount:.2f}"


class NotificationService:
    def notify(self, message):
        return f"Notification sent: {message}"


def demo():
    order_service = OrderService()
    payment_service = PaymentService()
    notification_service = NotificationService()

    order = order_service.create_order("Notebook", 2)
    return [
        f"Order created: {order}",
        payment_service.pay(12.00),
        notification_service.notify("Order confirmed"),
    ]
