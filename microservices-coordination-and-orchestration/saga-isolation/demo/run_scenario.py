#!/usr/bin/env python3
"""End-to-end deterministic competing-sagas demonstration.

Use while Docker Compose services are running. Only the Python stdlib is needed
on the host. A *durable outbox gate*, rather than sleep-based race timing,
holds the ApproveOrder command until the CancelOrder Saga reaches its end.
"""
import argparse
import json
import os
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE = os.getenv('ORDER_API', 'http://localhost:8001')
TIMEOUT = int(os.getenv('SCENARIO_TIMEOUT', '90'))


def api(method, path, data=None, expected=200):
    req = Request(BASE + path, data=(json.dumps(data).encode() if data is not None
               else b'' if method == 'POST' else None), method=method,
               headers={'Content-Type': 'application/json'})
    try:
        with urlopen(req, timeout=8) as response:
            status, body = response.status, json.loads(response.read())
    except HTTPError as error:
        status, body = error.code, json.loads(error.read())
    if status != expected:
        raise RuntimeError(f'{method} {path}: expected HTTP {expected}, got {status}: {body}')
    return body


def until(path, field, expected):
    deadline = time.monotonic() + TIMEOUT
    last = None
    while time.monotonic() < deadline:
        last = api('GET', path)
        if last.get(field) == expected:
            return last
        time.sleep(.2)  # Polling only; the race is controlled by the durable gate.
    raise RuntimeError(f'Timeout waiting for {path}.{field}={expected}; last={last}')


def run(mode):
    created = api('POST', '/orders', {'customerId': 'CUST_1', 'amount': 42,
                                     'isolationMode': mode}, expected=202)
    oid = created['orderId']
    print(f'Order: {oid}   mode={mode}', flush=True)
    path = '/orders/' + oid
    until(path + '/gate', 'gate', 'PAUSED')
    print('CreateOrder reached APPROVE_ORDER; its outgoing ApproveOrder is HELD.', flush=True)
    if mode == 'semantic':
        rejected = api('POST', path + '/cancel', expected=409)
        print(f'Semantic lock refused concurrent cancellation: {rejected}', flush=True)
        api('POST', path + '/release', expected=200)
        until(path, 'status', 'APPROVED')
        print('CreateOrder completed; now start an ordinary CancelOrder Saga.', flush=True)
        api('POST', path + '/cancel', expected=202)
        until(path, 'cancelStage', 'CANCELLED')
        result = until(path, 'status', 'CANCELLED')
        assert result['stage'] == 'APPROVED', result
        print('SUCCESS: semantic lock rejected concurrency; later cancellation completed.', flush=True)
    else:
        api('POST', path + '/cancel', expected=202)
        until(path, 'cancelStage', 'CANCELLED')
        print('CancelOrder completed: authorization VOIDED, ticket REJECTED, order CANCELLED.', flush=True)
        api('POST', path + '/release', expected=200)
        final_stage = 'APPROVED' if mode == 'unsafe' else 'CANCELLED'
        result = until(path, 'stage', final_stage)
        final_status = 'APPROVED' if mode == 'unsafe' else 'CANCELLED'
        assert result['status'] == final_status, result
        if mode == 'unsafe':
            print('EXPECTED ANOMALY: late approval overwrote CANCELLED -> APPROVED!', flush=True)
        else:
            print('SUCCESS: optimistic version check rejected stale ApproveOrder.', flush=True)
    print('Final order:', json.dumps(result, indent=2), flush=True)
    print('CreateOrder history:', json.dumps(api('GET', path + '/history')['history'], indent=2), flush=True)
    print('CancelOrder history:', json.dumps(api('GET', path + '/cancel/history')['history'], indent=2), flush=True)
    print('Inspect postgres_order, postgres_kitchen, postgres_accounting in Adminer.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('unsafe', 'semantic', 'optimistic'))
    args = parser.parse_args()
    try:
        run(args.mode)
    except (OSError, URLError, RuntimeError, AssertionError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
