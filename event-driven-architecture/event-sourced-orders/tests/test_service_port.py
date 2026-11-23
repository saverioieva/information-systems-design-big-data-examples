"""Application and inbound-adapter tests without the eventsourcing library or a database."""
from uuid import uuid4
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.application.errors import ConcurrencyError, OrderNotFound
from app.application.order_service import OrderService
from app.adapters.inbound.http_api import create_router

class OrderResult:
    def __init__(self, order_id):
        self.id = order_id
        self.consumer_id = 'consumer'
        self.restaurant_id = 'restaurant'
        self.state = type('State', (), {'value': 'APPROVAL_PENDING'})()
        self.line_items = []
        self.order_total = 5.0
        self.version = 1
        self.row_version = 1
        self.state_version = 1
        self.aggregate_schema_version = 1
        self.event_schema_version = 1

class FakeOrderStore:
    def __init__(self):
        self.orders = {}
    def create_order(self, consumer_id, restaurant_id, items):
        order_id = uuid4()
        self.orders[order_id] = OrderResult(order_id)
        return order_id
    def get_order(self, order_id):
        if order_id not in self.orders:
            raise OrderNotFound(order_id)
        return self.orders[order_id]
    def get_order_version(self, order_id, version):
        return self.get_order(order_id)
    def approve_order(self, order_id, expected_version=None):
        order = self.get_order(order_id)
        if expected_version != order.version:
            raise ConcurrencyError('Version mismatch')
        order.state = type('State', (), {'value': 'APPROVED'})()
        order.version += 1
        order.row_version += 1
    def cancel_order(self, order_id, expected_version=None):
        return None
    def add_item_to_order(self, *args, **kwargs):
        return None


def test_application_calls_port_without_framework():
    store = FakeOrderStore()
    service = OrderService(store)
    created = service.create_order('c', 'r', [])
    service.approve_order(created.id, 1)
    assert service.get_order(created.id).state.value == 'APPROVED'


def test_fastapi_adapter_maps_conflicts_from_service():
    store = FakeOrderStore()
    app = FastAPI()
    app.include_router(create_router(OrderService(store)))
    client = TestClient(app)
    created = client.post('/orders', json={'consumer_id':'c','restaurant_id':'r',
        'line_items':[{'menu_item_id':'A','name':'A','price':5,'quantity':1}]})
    assert created.status_code == 201
    order_id = created.json()['id']
    assert client.post(f'/orders/{order_id}/approve',json={'expected_version':1}).status_code == 200
    assert client.post(f'/orders/{order_id}/approve',json={'expected_version':1}).status_code == 409
