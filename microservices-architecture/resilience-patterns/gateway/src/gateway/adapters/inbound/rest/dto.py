from __future__ import annotations

from gateway.domain.models import Delivery, KitchenTicket, Order, OrderView, Payment


def order_to_dict(value: Order) -> dict:
    return {"orderId": value.order_id, "items": value.items, "status": value.status}


def kitchen_to_dict(value: KitchenTicket) -> dict:
    return {
        "orderId": value.order_id,
        "ticketId": value.ticket_id,
        "status": value.status,
        "station": value.station,
    }


def delivery_to_dict(value: Delivery) -> dict:
    return {
        "orderId": value.order_id,
        "deliveryId": value.delivery_id,
        "etaMinutes": value.eta_minutes,
        "status": value.status,
    }


def payment_to_dict(value: Payment) -> dict:
    result = {
        "orderId": value.order_id,
        "paymentId": value.payment_id,
        "amount": value.amount,
        "currency": value.currency,
        "method": value.method,
        "status": value.status,
    }
    if value.source is not None:
        result["source"] = value.source
    return result


def model_to_dict(value):
    if isinstance(value, Order):
        return order_to_dict(value)
    if isinstance(value, KitchenTicket):
        return kitchen_to_dict(value)
    if isinstance(value, Delivery):
        return delivery_to_dict(value)
    if isinstance(value, Payment):
        return payment_to_dict(value)
    raise TypeError(f"Unsupported REST DTO source: {type(value)!r}")


def order_view_to_dict(view: OrderView) -> dict:
    return {
        "order": order_to_dict(view.order),
        "kitchen": kitchen_to_dict(view.kitchen) if view.kitchen else None,
        "delivery": delivery_to_dict(view.delivery) if view.delivery else None,
        "payment": payment_to_dict(view.payment) if view.payment else None,
        "degraded": view.degraded,
        "missing": view.missing,
        "fallbacks": view.fallbacks,
    }
