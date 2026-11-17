"""Serialize a read-only aggregate snapshot for external clients."""

from dataclasses import asdict
from app.domain.models import Order


def order_to_dict(order: Order):
    return {
        'id': order.id,
        'consumer_id': order.consumer_id,
        'restaurant_id': order.restaurant_id,
        'state': order.state.value,
        'address': asdict(order.address) if order.address else None,
        'lines': [{
            'line_id': line.line_id,
            'menu_item_id': line.menu_item_id,
            'name': line.name,
            'unit_price': line.unit_price.as_dict(),
            'quantity': line.quantity,
            'subtotal': line.subtotal.as_dict(),
        } for line in order.lines],
        'total': order.total.as_dict(),
        'row_version': order.row_version,
    }
