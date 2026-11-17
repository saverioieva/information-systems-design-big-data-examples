from decimal import Decimal
from typing import Dict, Any



def line_item_to_dict(li) -> Dict[str, Any]:
    return {
        "menu_item_id": li.menu_item_id,
        "name": li.name,
        "price": Decimal(str(li.price)),
        "quantity": li.quantity,
        "subtotal": Decimal(str(li.subtotal)),
    }


def order_to_dict(order) -> Dict[str, Any]:
    return {
        "id": order.id,
        "consumer_id": order.consumer_id,
        "restaurant_id": order.restaurant_id,
        "state": getattr(order.state, "value", order.state),
        "line_items": [line_item_to_dict(li) for li in order.line_items],
        "order_total": Decimal(str(order.order_total)),
        "row_version": order.row_version,
        "state_version": order.state_version,
        "aggregate_schema_version": order.aggregate_schema_version,
        "event_schema_version": order.event_schema_version,
    }
