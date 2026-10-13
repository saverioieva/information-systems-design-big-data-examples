from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request

from order_service.application.ports.inbound.order_use_cases import OrderUseCases
from order_service.domain.order import Order


def _order_to_response(order: Order) -> dict[str, object]:
    assert order.id is not None
    return {
        "id": order.id,
        "restaurantId": order.restaurant_id,
        "status": order.status,
        "total": float(order.total),
    }


def _bad_request(message: str):
    return jsonify({"detail": message}), 400


def build_order_blueprint(use_cases: OrderUseCases) -> Blueprint:
    """Flask inbound adapter: HTTP/JSON <-> inbound-port translation."""

    blueprint = Blueprint("orders", __name__, url_prefix="/orders")

    @blueprint.post("")
    def create_order():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return _bad_request("Request body must be a JSON object")

        restaurant_id = payload.get("restaurantId")
        raw_total = payload.get("total")

        if not isinstance(restaurant_id, int) or isinstance(restaurant_id, bool):
            return _bad_request("restaurantId must be an integer")

        if isinstance(raw_total, bool) or not isinstance(raw_total, (int, float)):
            return _bad_request("total must be a number")

        try:
            total = Decimal(str(raw_total))
        except (InvalidOperation, ValueError):
            return _bad_request("total must be a number")

        try:
            order = use_cases.create_order(restaurant_id, total)
        except ValueError as exc:
            return _bad_request(str(exc))

        return jsonify(_order_to_response(order)), 201

    @blueprint.get("/<int:order_id>")
    def get_order(order_id: int):
        order = use_cases.get_order(order_id)
        if order is None:
            return jsonify({"detail": "Order not found"}), 404
        return jsonify(_order_to_response(order)), 200

    return blueprint
