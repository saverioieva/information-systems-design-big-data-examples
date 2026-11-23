from app.application.order_service import OrderService, OrderNotFound
from app.domain.models import OrderLineItem, ConcurrencyError

class FakeUow:
    def __init__(self, records):
        self.records = records
        self.orders = self
        self.commits = 0
    def __enter__(self): return self
    def __exit__(self, exc_type, exc, tb): pass
    def add(self, order):
        order.row_version = 1
        self.records[order.id] = order
    def get(self, order_id): return self.records.get(order_id)
    def save(self, order):
        order.row_version += 1
    def commit(self): self.commits += 1


def test_service_uses_port_without_postgres_or_http():
    records = {}
    service = OrderService(lambda: FakeUow(records))
    order = service.create('c','r',[OrderLineItem('p','Pizza',6.0,1)])
    assert service.approve(order.id, expected_version=1).state.value == 'APPROVED'
    try:
        service.cancel(order.id, expected_version=1)
        assert False, 'Expected a concurrency error'
    except ConcurrencyError:
        pass
    try:
        service.get('missing')
        assert False, 'Expected a missing order'
    except OrderNotFound:
        pass
