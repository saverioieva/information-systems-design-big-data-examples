import inventory_pb2
from common import stub

channel, client = stub()
for update in client.WatchStock(inventory_pb2.WatchStockRequest(sku="pizza")):
    print(f"{update.sku}: {update.available_quantity}")
channel.close()
