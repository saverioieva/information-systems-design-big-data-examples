from typing import Any, Dict

from eventsourcing.persistence import Transcoding

from app.domain.models import OrderLineItem


class OrderLineItemAsDict(Transcoding):
    """
    Transcoding that represents OrderLineItem as a plain dict,
    so snapshots (and events if needed) can be JSON-encoded.
    """

    type = OrderLineItem
    name = "order_line_item"

    def encode(self, obj: OrderLineItem) -> Dict[str, Any]:
        return {
            "menu_item_id": obj.menu_item_id,
            "name": obj.name,
            "price": obj.price,
            "quantity": obj.quantity,
        }

    def decode(self, data: Dict[str, Any]) -> OrderLineItem:
        assert isinstance(data, dict)
        return OrderLineItem(
            menu_item_id=data["menu_item_id"],
            name=data["name"],
            price=float(data["price"]),
            quantity=int(data["quantity"]),
        )
