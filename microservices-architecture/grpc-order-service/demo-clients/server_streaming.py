import order_pb2
from common import stub

channel, client = stub()
created = client.CreateOrder(
    order_pb2.CreateOrderRequest(restaurant_id="rest-1", item="pasta", quantity=1)
)
for update in client.WatchOrder(order_pb2.WatchOrderRequest(order_id=created.order_id)):
    print(order_pb2.OrderStatus.Name(update.status))
channel.close()
