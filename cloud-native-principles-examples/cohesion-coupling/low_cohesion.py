class OrderManager:
    def create_order(self, product, quantity):
        return {"product": product, "quantity": quantity}

    def pay(self, amount):
        return f"Payment completed: EUR {amount:.2f}"

    def notify(self, message):
        return f"Notification sent: {message}"


def demo():
    manager = OrderManager()
    order = manager.create_order("Notebook", 2)
    return [
        f"Order created: {order}",
        manager.pay(12.00),
        manager.notify("Order confirmed"),
    ]
