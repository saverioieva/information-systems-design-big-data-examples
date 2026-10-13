from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient
from flask import Flask

from order_service.adapters.inbound.fastapi.routes import build_order_router
from order_service.adapters.inbound.flask.routes import build_order_blueprint
from order_service.application.ports.inbound.order_use_cases import OrderUseCases
from order_service.domain.order import Order


class FakeOrderUseCases(OrderUseCases):
    """A fake inbound-port implementation used to test adapters in isolation."""

    def __init__(self) -> None:
        self.order: Order | None = None

    def create_order(self, restaurant_id: int, total: Decimal) -> Order:
        self.order = Order(
            id=7,
            restaurant_id=restaurant_id,
            status="CREATED",
            total=total,
        )
        return self.order

    def get_order(self, order_id: int) -> Order | None:
        if self.order is not None and self.order.id == order_id:
            return self.order
        return None


def test_fastapi_adapter_depends_only_on_inbound_port() -> None:
    use_cases = FakeOrderUseCases()
    app = FastAPI()
    app.include_router(build_order_router(use_cases))
    client = TestClient(app)

    created = client.post("/orders", json={"restaurantId": 42, "total": 25.50})
    fetched = client.get("/orders/7")

    assert created.status_code == 201
    assert created.json() == {
        "id": 7,
        "restaurantId": 42,
        "status": "CREATED",
        "total": 25.5,
    }
    assert fetched.status_code == 200
    assert fetched.json() == created.json()


def test_flask_adapter_depends_only_on_inbound_port() -> None:
    use_cases = FakeOrderUseCases()
    app = Flask(__name__)
    app.register_blueprint(build_order_blueprint(use_cases))
    client = app.test_client()

    created = client.post("/orders", json={"restaurantId": 42, "total": 25.50})
    fetched = client.get("/orders/7")

    assert created.status_code == 201
    assert created.get_json() == {
        "id": 7,
        "restaurantId": 42,
        "status": "CREATED",
        "total": 25.5,
    }
    assert fetched.status_code == 200
    assert fetched.get_json() == created.get_json()
