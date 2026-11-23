"""Instructor-run, noninteractive state-based persistence demo."""
import json
from http_client import request
BASE="http://localhost:8101/orders"
def show(label,data):
    print(f"\n{label}\n{json.dumps(data,indent=2)}")

_,created=request("POST",BASE,{"consumer_id":"c-1","restaurant_id":"r-1",
    "line_items":[{"menu_item_id":"pizza","name":"Pizza","price":8.0,"quantity":1}]},expected=(201,),retries=20)
order_id=created["id"];v1=created["row_version"]
show("1. Created current-state order (v1)",created)
_,updated=request("POST",f"{BASE}/{order_id}/items",{"menu_item_id":"water","name":"Water",
  "price":2.0,"quantity":1,"expected_version":v1})
show("2. SQL rows overwritten with updated current state (v2)",updated)
status,conflict=request("POST",f"{BASE}/{order_id}/approve",{"expected_version":v1},expected=(409,))
show(f"3. Stale version rejected with HTTP {status}",conflict)
_,approved=request("POST",f"{BASE}/{order_id}/approve",{"expected_version":updated["row_version"]})
show("4. Approved, new current state stored",approved)
print("\nObserve: the ordinary orders table has ONE current row for this ID, not its full history.")
