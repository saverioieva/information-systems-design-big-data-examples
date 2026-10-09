import order_pb2
from common import stub

channel, client = stub()
reply = client.CreateOrder(
    order_pb2.CreateOrderRequest(restaurant_id="rest-1", item="pizza", quantity=2)
)
print(reply)
channel.close()
