"""HTTP-level tests: no business workflow bypasses the inbound adapter."""
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.adapters.inbound.http_api import get_order_service, router
from app.adapters.outbound.sqlalchemy_uow import SqlAlchemyUnitOfWork
from app.application.order_service import OrderService
from tests.common import create_payload, line_payload, sqlite_sessions


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.engine, sessions = sqlite_sessions()
        self.app = FastAPI()
        self.app.include_router(router)
        self.app.dependency_overrides[get_order_service] = lambda: OrderService(
            lambda: SqlAlchemyUnitOfWork(sessions)
        )
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self.engine.dispose()

    def create(self, payload=None):
        response = self.client.post('/orders', json=payload or create_payload())
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_full_lifecycle_uses_http_and_aggregate_root(self):
        created = self.create()
        order_id = created['id']
        line_id = created['lines'][0]['line_id']
        self.assertEqual(created['total'], {'amount': '20.00', 'currency': 'EUR'})
        self.assertEqual(created['row_version'], 1)

        res = self.client.patch(f'/orders/{order_id}/lines/{line_id}', json={
            'quantity': 3, 'expected_version': 1
        })
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()['lines'][0]['line_id'], line_id)
        self.assertEqual(res.json()['total']['amount'], '30.00')
        self.assertEqual(res.json()['row_version'], 2)

        res = self.client.put(f'/orders/{order_id}/address', json={
            'address': {'street': 'Via Roma 1', 'city': 'Bari',
                        'postal_code': '70100', 'country': 'IT'},
            'expected_version': 2,
        })
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()['address']['city'], 'Bari')

        res = self.client.post(f'/orders/{order_id}/approve?expected_version=3')
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()['state'], 'APPROVED')
        self.assertEqual(self.client.get(f'/orders/{order_id}').json()['row_version'], 4)

        res = self.client.patch(f'/orders/{order_id}/lines/{line_id}', json={'quantity': 4})
        self.assertEqual(res.status_code, 400)
        self.assertIn('pending', res.json()['detail'])

    def test_new_entity_is_added_by_rest_endpoint(self):
        created = self.create()
        res = self.client.post(f"/orders/{created['id']}/lines", json={
            **line_payload('WATER', '2.00', 3), 'expected_version': 1,
        })
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(len(res.json()['lines']), 2)
        self.assertEqual(res.json()['total']['amount'], '26.00')
        self.assertEqual(len({line['line_id'] for line in res.json()['lines']}), 2)

    def test_last_line_removal_is_rejected_by_root(self):
        created = self.create()
        res = self.client.delete(f"/orders/{created['id']}/lines/{created['lines'][0]['line_id']}")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(self.client.get(f"/orders/{created['id']}").json()['row_version'], 1)

    def test_approval_requires_address_and_minimum_amount(self):
        created = self.create()
        res = self.client.post(f"/orders/{created['id']}/approve")
        self.assertEqual(res.status_code, 400)
        cheap = self.create(create_payload([line_payload(price='1.00')]))
        res = self.client.put(f"/orders/{cheap['id']}/address", json={
            'address': {'street': 'Via Roma', 'city': 'Bari',
                        'postal_code': '70100', 'country': 'IT'}
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.client.post(f"/orders/{cheap['id']}/approve").status_code, 400)

    def test_stale_version_is_http_409(self):
        created = self.create()
        url = f"/orders/{created['id']}/lines/{created['lines'][0]['line_id']}"
        first = self.client.patch(url, json={'quantity': 3, 'expected_version': 1})
        self.assertEqual(first.status_code, 200)
        stale = self.client.patch(url, json={'quantity': 4, 'expected_version': 1})
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(self.client.get(f"/orders/{created['id']}").json()['lines'][0]['quantity'], 3)

    def test_cross_line_business_rule_is_http_400(self):
        created = self.create()
        res = self.client.post(f"/orders/{created['id']}/lines", json={
            **line_payload('EXTRA', '190.00', 1), 'expected_version': 1
        })
        self.assertEqual(res.status_code, 400)
        self.assertEqual(len(self.client.get(f"/orders/{created['id']}").json()['lines']), 1)

    def test_duplicate_menu_and_mixed_currencies_rejected(self):
        duplicate = self.client.post('/orders', json=create_payload([line_payload(), line_payload()]))
        self.assertEqual(duplicate.status_code, 400)
        mixed = self.client.post('/orders', json=create_payload([
            line_payload(), line_payload('TEA', '3.00', 1, 'USD')
        ]))
        self.assertEqual(mixed.status_code, 400)

    def test_request_validation_and_missing_resource(self):
        bad = self.client.post('/orders', json=create_payload([line_payload(qty=0)]))
        self.assertEqual(bad.status_code, 422)
        self.assertEqual(self.client.get('/orders/unknown').status_code, 404)
        created = self.create()
        self.assertEqual(self.client.patch(f"/orders/{created['id']}/lines/unknown",
                         json={'quantity': 2}).status_code, 404)

    def test_cancel_is_a_domain_transition_not_physical_deletion(self):
        created = self.create()
        res = self.client.post(f"/orders/{created['id']}/cancel?expected_version=1")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['state'], 'CANCELLED')
        self.assertEqual(self.client.get(f"/orders/{created['id']}").status_code, 200)


if __name__ == '__main__':
    unittest.main()
