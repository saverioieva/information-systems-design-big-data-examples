#!/usr/bin/env python3
"""Run a distributed countermeasure workflow via REST; observe RabbitMQ replies.

Requires running Compose services. The script never opens a SQL connection and
never calls a participant directly: it polls the Order Service's durable status.
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


def request(method, path):
    req = Request(BASE + path, method=method,
                  data=b'' if method == 'POST' else None,
                  headers={'Content-Type': 'application/json'})
    with urlopen(req, timeout=8) as response:
        data = json.loads(response.read())
        return response.status, data


def run(kind):
    deadline = time.monotonic() + TIMEOUT
    while True:
        try:
            status, result = request('POST', '/countermeasures/' + kind)
            assert status == 202
            break
        except (OSError, URLError):
            if time.monotonic() > deadline:
                raise
            time.sleep(.4)
    run_id = result['runId']
    print(f'Started distributed {kind} run {run_id} through REST', flush=True)
    last = None
    while time.monotonic() < deadline:
        _, last = request('GET', '/countermeasures/' + run_id)
        if last['status'] in ('COMPLETED', 'REJECTED'):
            break
        time.sleep(.2)
    if last['status'] != 'COMPLETED':
        raise RuntimeError(f'{kind} did not finish: {last}')

    steps = last['steps']
    if kind == 'commutative':
        credits = [s for s in steps if s['name'] == 'credit']
        duplicate = next(s for s in steps if s['name'] == 'duplicate')
        compensation = next(s for s in steps if s['name'] == 'compensation')
        if len(credits) != 4 or not all(s['status'] == 'DONE' for s in steps):
            raise AssertionError(f'Not all credit Saga steps completed: {steps}')
        if duplicate['result']['balance'] != 115 or compensation['result']['balance'] != 90:
            raise AssertionError(f'Idempotency/compensation mismatch: {steps}')
        # One Accounting consumer serializes operations in each account. The
        # final credit reply for each account must be 115 before compensation.
        for label in ('A', 'B'):
            ops = [s for s in credits if s['data']['case'] == label]
            if sorted(s['data']['delta'] for s in ops) != [-10, 25]:
                raise AssertionError(ops)
            if 115 not in [s['result']['balance'] for s in ops]:
                raise AssertionError(f'Account {label} did not reach 115: {ops}')
        print('COMMUTATIVE: two credit sagas per account -> 100 +25 -10 = 115')
        print('Duplicate +25 did not apply twice: 115; compensation -25 -> 90')
        print('Verified via Consumer -> RabbitMQ -> Accounting PostgreSQL -> reply.orchestrator')
    else:
        versions = {s['data']['sequence']: s for s in steps}
        expected = {3: {'nextSequence': 1, 'total': 0, 'buffered': 1},
                    1: {'nextSequence': 2, 'total': 10, 'buffered': 1},
                    2: {'nextSequence': 4, 'total': 27, 'buffered': 0}}
        if len(versions) != 3 or any(versions[n]['result'] != state
                                     for n, state in expected.items()):
            raise AssertionError(f'Version File state mismatch: {versions}')
        print('VERSION FILE: Kitchen received seq 3 -> 1 -> 2 through RabbitMQ')
        print('  seq 3 buffered (0), seq 1 applied (10), seq 2 drains 2 and 3 (27)')
        print('Verified via Consumer -> RabbitMQ -> Kitchen PostgreSQL -> reply.orchestrator')
    print(f'Durable run status: {BASE}/countermeasures/{run_id}', flush=True)
    return last


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind', choices=('commutative', 'version-file'))
    args = parser.parse_args()
    try:
        run(args.kind)
    except (AssertionError, RuntimeError, HTTPError, URLError, OSError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
