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


def wait_for_api():
    # Compose can report containers as started before the HTTP app is ready.
    deadline = time.monotonic() + TIMEOUT
    last_error = None
    while time.monotonic() < deadline:
        try:
            api('GET', '/openapi.json')
            return
        except (OSError, URLError, RuntimeError, ValueError) as exc:
            last_error = exc
            time.sleep(.4)
    raise RuntimeError(f'Order API not ready at {BASE}: {last_error}')


def run(mode, amount=42, summary=False):
    created = api('POST', '/orders', {'customerId': 'CUST_1', 'amount': amount,
                                     'isolationMode': mode}, expected=202)
    oid = created['orderId']
    effective_mode = created['isolationMode']
    print(f'Order: {oid} requested={mode} selected={effective_mode} amount={amount}', flush=True)
    path = '/orders/' + oid
    until(path + '/gate', 'gate', 'PAUSED')
    print('CreateOrder reached APPROVE_ORDER; its outgoing ApproveOrder is HELD.', flush=True)
    if effective_mode == 'semantic':
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
    elif effective_mode == 'pessimistic':
        api('POST', path + '/cancel', expected=202)
        until(path + '/cancel/gate', 'gate', 'PAUSED')
        pending = until(path, 'status', 'CANCELLATION_PENDING')
        assert pending['cancelStage'] == 'VOID_AUTHORIZATION', pending
        print('PESSIMISTIC VIEW: Order already CANCELLATION_PENDING while the')
        print('compensating authorization command is deliberately held.')
        api('POST', path + '/release', expected=200)
        skipped = until(path, 'stage', 'SUPERSEDED')
        assert skipped['status'] == 'CANCELLATION_PENDING', skipped
        print('Stale approval rechecked the current status and was skipped.')
        api('POST', path + '/cancel/release', expected=200)
        until(path, 'cancelStage', 'CANCELLED')
        result = until(path, 'status', 'CANCELLED')
        print('SUCCESS: protective status-before-effects + reread; no premature APPROVED.')
    else:
        api('POST', path + '/cancel', expected=202)
        until(path, 'cancelStage', 'CANCELLED')
        print('CancelOrder completed: authorization VOIDED, ticket REJECTED, order CANCELLED.', flush=True)
        api('POST', path + '/release', expected=200)
        final_stage = 'APPROVED' if effective_mode == 'unsafe' else 'SUPERSEDED'
        result = until(path, 'stage', final_stage)
        final_status = 'APPROVED' if effective_mode == 'unsafe' else 'CANCELLED'
        assert result['status'] == final_status, result
        if effective_mode == 'unsafe':
            print('EXPECTED ANOMALY: late approval overwrote CANCELLED -> APPROVED!', flush=True)
        elif effective_mode == 'optimistic':
            print('SUCCESS: atomic status+version compare rejected stale ApproveOrder.', flush=True)
        else:
            print('SUCCESS: Reread Value prevented a stale ApproveOrder.', flush=True)
    print(f'RESULT: mode={effective_mode} status={result["status"]} '
          f'createStage={result["stage"]} cancelStage={result["cancelStage"]}', flush=True)
    if not summary:
        print('Final order:', json.dumps(result, indent=2), flush=True)
        print('CreateOrder history:', json.dumps(api('GET', path + '/history')['history'], indent=2), flush=True)
        print('CancelOrder history:', json.dumps(api('GET', path + '/cancel/history')['history'], indent=2), flush=True)
        print('Inspect postgres_order, postgres_kitchen, postgres_accounting in Adminer.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('unsafe', 'semantic', 'optimistic', 'reread', 'pessimistic', 'by_value'))
    parser.add_argument('--summary', action='store_true', help='Show a compact final-state summary')
    args = parser.parse_args()
    try:
        wait_for_api()
        if args.mode == 'by_value':
            run('by_value', amount=42, summary=args.summary)   # Low risk -> reread
            run('by_value', amount=90, summary=args.summary)   # High risk -> semantic lock
        else:
            run(args.mode, summary=args.summary)
    except (OSError, URLError, RuntimeError, AssertionError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
