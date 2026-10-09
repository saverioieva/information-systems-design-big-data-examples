import order_pb2
from common import stub


def requests():
    for item in ("pizza", "pasta", "salad"):
        yield order_pb2.CreateOrderRequest(
            restaurant_id="rest-1",
            item=item,
            quantity=1,
        )


channel, client = stub()
reply = client.BulkCreateOrders(requests())
print(f"created={reply.created}")
for order_id in reply.order_ids:
    print(order_id)
channel.close()
