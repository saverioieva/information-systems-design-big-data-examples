import inventory_pb2
from common import stub


def requests():
    for sku, quantity in (("pizza", 2), ("pasta", 5), ("salad", 1)):
        yield inventory_pb2.CheckAvailabilityRequest(sku=sku, quantity=quantity)


channel, client = stub()
reply = client.CheckMany(requests())
print(f"checked={reply.checked}, available={reply.available_count}")
for item in reply.results:
    print(f"{item.sku}: requested={item.requested_quantity}, stock={item.available_quantity}, available={item.available}")
channel.close()
