from app.domain.models import Order

def order_to_dict(order: Order):
    return {
        "id": order.id,
        "consumer_id": order.consumer_id,
        "restaurant_id": order.restaurant_id,
        "state": order.state.value,
        "line_items": [
            {
                "menu_item_id": li.menu_item_id,
                "name": li.name,
                "price": li.price,
                "quantity": li.quantity,
                "subtotal": li.subtotal,
            }
            for li in order.line_items
        ],
        "order_total": order.order_total,
        "row_version": order.row_version,
    }
