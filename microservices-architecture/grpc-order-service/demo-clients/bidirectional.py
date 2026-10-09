import order_pb2
from common import stub

channel, client = stub()
created = client.CreateOrder(
    order_pb2.CreateOrderRequest(restaurant_id="rest-1", item="pizza", quantity=1)
)


def commands():
    for action in ("accept", "prepare", "ready"):
        yield order_pb2.OrderCommand(order_id=created.order_id, action=action)


for event in client.OrderConversation(commands()):
    print(event.message)
channel.close()
