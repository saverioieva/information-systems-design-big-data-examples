"""Use the running REST API to exercise the aggregate boundary end-to-end.

Run after `make up` with `make demo`. Only HTTP requests, no direct database
writes and no Python access to internal domain objects.
"""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE_URL = os.getenv('BASE_URL', 'http://localhost:8003').rstrip('/')


def request(method, path, payload=None, expected_status=200):
    content = None if payload is None else json.dumps(payload).encode('utf-8')
    req = Request(BASE_URL + path, data=content, method=method,
                  headers={'Content-Type': 'application/json'} if content is not None else {})
    try:
        with urlopen(req, timeout=12) as response:
            status = response.status
            data = json.loads(response.read())
    except HTTPError as exc:
        status = exc.code
        data = json.loads(exc.read())
    if status != expected_status:
        raise AssertionError(f'{method} {path}: expected HTTP {expected_status}, got {status}: {data}')
    return data


def show(step, response):
    print(f'{step}: state={response["state"]}, total={response["total"]["amount"]} '
          f'{response["total"]["currency"]}, version={response["row_version"]}')


def main():
    created = request('POST', '/orders', {
        'consumer_id': 'CUST_1', 'restaurant_id': 'REST_1',
        'lines': [{
            'menu_item_id': 'PIZZA', 'name': 'Pizza', 'quantity': 2,
            'unit_price': {'amount': '10.00', 'currency': 'EUR'}
        }]
    }, 201)
    order_id = created['id']
    pizza_line_id = created['lines'][0]['line_id']
    show('1. Create via HTTP', created)

    added = request('POST', f'/orders/{order_id}/lines', {
        'menu_item_id': 'WATER', 'name': 'Water', 'quantity': 3,
        'unit_price': {'amount': '2.00', 'currency': 'EUR'}, 'expected_version': 1
    })
    show('2. Add a child entity through Order', added)

    changed = request('PATCH', f'/orders/{order_id}/lines/{pizza_line_id}', {
        'quantity': 3, 'expected_version': 2
    })
    assert changed['lines'][0]['line_id'] == pizza_line_id or any(
        line['line_id'] == pizza_line_id for line in changed['lines']
    )
    show('3. Modify quantity while preserving line identity', changed)

    address = request('PUT', f'/orders/{order_id}/address', {
        'address': {'street': 'Via Roma 1', 'city': 'Bari',
                    'postal_code': '70100', 'country': 'IT'}, 'expected_version': 3
    })
    show('4. Replace the Address value object', address)

    request('PATCH', f'/orders/{order_id}/lines/{pizza_line_id}', {
        'quantity': 4, 'expected_version': 2
    }, 409)
    print('5. Stale request rejected with HTTP 409')

    request('POST', f'/orders/{order_id}/lines', {
        'menu_item_id': 'EXPENSIVE', 'name': 'Expensive item', 'quantity': 1,
        'unit_price': {'amount': '190.00', 'currency': 'EUR'},
        'expected_version': 4
    }, 400)
    print('6. Cross-line total invariant rejected with HTTP 400')

    approved = request('POST', f'/orders/{order_id}/approve?expected_version=4')
    show('7. Approve after passing all invariants', approved)

    request('PATCH', f'/orders/{order_id}/lines/{pizza_line_id}', {'quantity': 4}, 400)
    print('8. Modification after approval rejected with HTTP 400')

    outbox = request('GET', '/lab/outbox')
    events = [item['eventType'] for item in outbox if item['aggregateId'] == order_id]
    expected = ['OrderCreated', 'OrderLineAdded', 'OrderLineQuantityChanged',
                'DeliveryAddressChanged', 'OrderApproved']
    assert set(events) == set(expected), (events, expected)
    print(f'9. Outbox domain facts: {", ".join(events)}')
    print(f'OK - all operations used the external REST API. Order ID: {order_id}')


if __name__ == '__main__':
    try:
        main()
    except URLError as exc:
        raise SystemExit('Cannot reach the API. Run `make up` first. ' + str(exc)) from exc
