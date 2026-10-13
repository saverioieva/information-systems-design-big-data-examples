import inventory_pb2
from common import stub


def commands():
    yield inventory_pb2.InventoryCommand(sku="pizza", action="check", quantity=1)
    yield inventory_pb2.InventoryCommand(sku="pizza", action="reserve", quantity=2)
    yield inventory_pb2.InventoryCommand(sku="pizza", action="release", quantity=1)


channel, client = stub()
for event in client.InventorySession(commands()):
    print(f"{event.sku}: {event.message}; stock={event.available_quantity}")
channel.close()
