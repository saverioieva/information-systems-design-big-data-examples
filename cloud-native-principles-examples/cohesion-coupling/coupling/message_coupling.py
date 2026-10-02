"""Message coupling: modules communicate through a narrow message/signal."""


class NotificationModule:
    def order_ready(self) -> str:
        return "notification: order ready"


class OrderModule:
    def __init__(self, on_order_ready):
        self.on_order_ready = on_order_ready

    def complete_order(self) -> str:
        # The collaborator is notified without receiving the order's internal data.
        return self.on_order_ready()


def demo() -> list[str]:
    notifications = NotificationModule()
    orders = OrderModule(notifications.order_ready)
    return [
        orders.complete_order(),
        "Observe: the modules communicate through a small signal, not shared internal state.",
    ]
