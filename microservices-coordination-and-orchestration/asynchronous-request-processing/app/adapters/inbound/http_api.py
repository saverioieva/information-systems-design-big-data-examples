"""Inbound HTTP adapter; no SQL or Pika imports."""
import logging
import sqlite3
import uuid
from flask import Flask, jsonify, request
from app.application.services import OrderUseCases
from app.adapters.outbound.sqlite_repository import SqliteOrderRepository
from app.adapters.outbound.rabbitmq import RabbitMQValidationPublisher

LOG = logging.getLogger(__name__)
app = Flask(__name__)
repository = SqliteOrderRepository()
service = OrderUseCases(repository, RabbitMQValidationPublisher())

@app.get("/health")
def health():
    return jsonify({"status": "ok"})

@app.post("/orders")
@app.post("/createOrder")
def create():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Expected a JSON object"}), 400
    order_id = str(data.get("order_id") or uuid.uuid4()).strip()
    consumer_id = str(data.get("consumer_id") or "CUST-1").strip()
    item = str(data.get("item") or "pizza").strip()
    if not all((order_id, consumer_id, item)) or max(map(len, (order_id, consumer_id, item))) > 128:
        return jsonify({"error": "Invalid order_id, consumer_id or item"}), 400
    try:
        output = service.create_order(order_id, consumer_id, item)
    except sqlite3.IntegrityError:
        return jsonify({"error": "Order already exists", "order_id": order_id}), 409
    except Exception:
        LOG.exception("Order %s saved but dispatch unconfirmed", order_id)
        return jsonify({"error": "Order saved, but dispatch could not be confirmed",
                        "order_id": order_id, "status_url": f"/orders/{order_id}"}), 503
    return jsonify(output), 202, {"Location": f"/orders/{order_id}"}

@app.get("/orders/<order_id>")
@app.get("/orderStatus/<order_id>")
def status(order_id):
    row = service.order(order_id)
    return (jsonify(row) if row else (jsonify({"error": "Order not found"}), 404))
