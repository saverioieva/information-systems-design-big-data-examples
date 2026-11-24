"""Live demo: same findOrder, live fan-out or a local CQRS read projection."""
from __future__ import annotations

import argparse
import json
import os
import time

import httpx

from scripts.demo import URLS, create, get, show, wait_for_saga

QUERY = os.getenv("QUERY_URL", "http://history:8000")
LAST_ORDER = "/shared/last-order-id"


def comparison(client: httpx.Client, oid: str, wait_projection: bool = True):
    expected = get(client, "order", f"/orders/{oid}").json()["status"]
    if wait_projection:
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            try:
                res = client.get(f"{QUERY}/find-order/{oid}/cqrs")
                if res.status_code == 200 and res.json()["order_status"] == expected and \
                        res.json()["payment_status"] in ("AUTHORIZED", "VOIDED") and \
                        res.json()["kitchen_status"] in ("ACCEPTED", "REJECTED"):
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.4)
        else:
            raise RuntimeError("Read model did not catch up; inspect query logs")
    for strategy in ("composition", "cqrs"):
        res = client.get(f"{QUERY}/find-order/{oid}/{strategy}", timeout=6)
        try:
            data = res.json()
        except ValueError:
            data = res.text
        print(f"{strategy:12s} HTTP {res.status_code}: {json.dumps(data, default=str)}")
        if strategy == "cqrs" and res.status_code == 200:
            timeline = client.get(f"{QUERY}/order-history/{oid}", timeout=6)
            timeline.raise_for_status()
            print(f"history      {len(timeline.json()['timeline'])} integration events in MongoDB timeline")
        if strategy == "cqrs":
            assert res.status_code == 200
    return oid


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=["compare", "compare-last"], default="compare")
    args = parser.parse_args()
    with httpx.Client(timeout=6) as client:
        if args.scenario == "compare":
            oid = create(client, reject=False)
            with open(LAST_ORDER, "w", encoding="utf-8") as fd:
                fd.write(oid)
            wait_for_saga(client, oid, "COMPLETED")
            show(client, oid)
        else:
            with open(LAST_ORDER, encoding="utf-8") as fd:
                oid = fd.read().strip()
            wait_for_saga(client, oid, "COMPLETED")
        comparison(client, oid)


if __name__ == "__main__":
    main()
