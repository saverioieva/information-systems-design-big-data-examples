"""Idempotent registration and health checking for two Debezium connectors."""
import json
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE = 'http://localhost:18083'
ROOT = Path(__file__).resolve().parents[1]
CONFIGS = [ROOT / 'connector/orders-raw.json', ROOT / 'connector/outbox-postgres.json']


def request(method, path, data=None):
    body = None if data is None else json.dumps(data).encode()
    req = Request(BASE + path, data=body, method=method,
                  headers={'Content-Type': 'application/json'})
    try:
        with urlopen(req, timeout=5) as r:
            return r.status, json.load(r)
    except HTTPError as e:
        return e.code, e.read().decode()


def wait_rest(attempts=60):
    for _ in range(attempts):
        try:
            code, _ = request('GET','/connectors')
            if code == 200:
                return
        except (URLError,TimeoutError,OSError):
            pass
        time.sleep(2)
    raise RuntimeError('Kafka Connect REST not reachable on localhost:18083')


def status():
    ok = True
    for path in CONFIGS:
        name = json.loads(path.read_text())['name']
        try:
            code, value = request('GET',f'/connectors/{name}/status')
        except (URLError,TimeoutError,OSError) as exc:
            print(f'[connect] {name}: REST unavailable: {exc}')
            return False
        if code != 200:
            print(f'[connect] {name}: HTTP {code}: {value}')
            ok = False
            continue
        tasks = value.get('tasks', [])
        states = [t.get('state') for t in tasks]
        print(f'[connect] {name}: connector={value["connector"]["state"]}, tasks={states}')
        ok &= value['connector']['state'] == 'RUNNING' and len(tasks) > 0 and all(s == 'RUNNING' for s in states)
    return ok


def register():
    wait_rest()
    for path in CONFIGS:
        value = json.loads(path.read_text())
        name = value['name']
        code, _ = request('GET',f'/connectors/{name}')
        if code == 200:
            print(f'[connect] {name} already registered; preserving offsets')
            continue
        for attempt in range(12):
            code, response = request('POST', '/connectors', value)
            if code in (200, 201):
                print(f'[connect] registered {name}: HTTP {code}')
                break
            if code == 409:
                # Kafka Connect may be rebalancing; retry rather than assuming success.
                existing, _ = request('GET', f'/connectors/{name}')
                if existing == 200:
                    print(f'[connect] {name} registered by another request')
                    break
                time.sleep(2)
                continue
            raise RuntimeError(f'Registration failed for {name}: {code} {response}')
        else:
            raise RuntimeError(f'{name} not registered after Kafka Connect rebalances')
    for _ in range(45):
        if status():
            return
        time.sleep(2)
    raise RuntimeError('Connector task not RUNNING; see docker compose logs connect')


if __name__ == '__main__':
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ('register','status'):
            raise ValueError('Usage: python3 scripts/register_connectors.py register|status')
        if sys.argv[1] == 'register':
            register()
        elif not status():
            raise RuntimeError('Connectors not all healthy/registered')
    except Exception as exc:
        print(f'[connect] ERROR: {exc}',file=sys.stderr)
        sys.exit(1)
