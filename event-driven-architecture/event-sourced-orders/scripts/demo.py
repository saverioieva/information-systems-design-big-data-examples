"""Instructor-run, noninteractive event-sourcing and replay demo."""
import json
from http_client import request
BASE="http://localhost:8102/orders"
def show(label,data):
    print(f"\n{label}\n{json.dumps(data,indent=2)}")
_,created=request("POST",BASE,{"consumer_id":"c-1","restaurant_id":"r-1",
    "line_items":[{"menu_item_id":"pizza","name":"Pizza","price":8.0,"quantity":1}]},expected=(201,),retries=20)
order_id=created["id"];v1=created["row_version"]
show("1. OrderCreated event (aggregate v1)",created)
_,updated=request("POST",f"{BASE}/{order_id}/items",{"menu_item_id":"water","name":"Water",
  "price":2.0,"quantity":1,"expected_version":v1})
show("2. Added line item (v2; snapshot interval is 2)",updated)
_,old=request("GET",f"{BASE}/{order_id}/versions/{v1}")
show("3. Historical replay up to v1 (water is absent)",old)
status,stale=request("POST",f"{BASE}/{order_id}/approve",{"expected_version":v1},expected=(409,))
show(f"4. Version conflict (HTTP {status})",stale)
_,approved=request("POST",f"{BASE}/{order_id}/approve",{"expected_version":updated["row_version"]})
show("5. OrderApproved event, current v3",approved)
print("\nObserve: event rows are append-only; snapshots accelerate reconstruction.")
