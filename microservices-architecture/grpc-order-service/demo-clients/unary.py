import inventory_pb2
from common import stub

channel, client = stub()
reply = client.CheckAvailability(
    inventory_pb2.CheckAvailabilityRequest(sku="pizza", quantity=2)
)
print(reply)
channel.close()
