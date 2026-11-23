"""Public runnable scenario: no direct database access or hidden test gates."""
from __future__ import annotations

import argparse
import json
import os
import time

import httpx
import pika

from lab.domain import message
from lab.messaging import EXCHANGE

URLS = {
    "order": os.getenv("ORDER_URL", "http://order:8000"),
    "accounting": os.getenv("ACCOUNTING_URL", "http://accounting:8000"),
    "kitchen": os.getenv("KITCHEN_URL", "http://kitchen:8000"),
    "orchestrator": os.getenv("SAGA_URL", "http://orchestrator:8000"),
}


def get(client, role, path):
    return client.get(URLS[role] + path)


def wait_for_saga(client, oid, expected, timeout=65):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            response = get(client, "orchestrator", f"/sagas/{oid}")
            if response.status_code == 200:
                state = response.json()
                if state["status"] == expected:
                    return state
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    raise RuntimeError(f"Saga for {oid} did not reach {expected}; inspect docker compose logs")


def show(client, oid):
    for role in ("order", "accounting", "kitchen", "orchestrator"):
        path = (f"/sagas/{oid}" if role == "orchestrator" else
                f"/internal/orders/{oid}" if role == "order" else
                f"/internal/authorizations/{oid}" if role == "accounting" else
                f"/internal/tickets/{oid}")
        state = get(client, role, path).json()
        events = get(client, role, f"/events/{oid}").json()["events"]
        print(f"{role:13s} state={state['status']:12s} v={state['version']:<2} "
              f"events={[ev['type'] for ev in events]}")


def send_duplicate(oid, event_data):
    duplicate = message("order.created", oid, event_data)
    url = os.getenv("RABBITMQ_URL", "amqp://lab:lab@rabbit:5672/%2F")
    conn = pika.BlockingConnection(pika.URLParameters(url))
    try:
        channel = conn.channel()
        channel.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)
        channel.confirm_delivery()
        channel.basic_publish(exchange=EXCHANGE, routing_key="order.created",
                              body=json.dumps(duplicate), mandatory=True,
                              properties=pika.BasicProperties(delivery_mode=2))
    finally:
        conn.close()


def create(client, reject):
    payload = {"consumer_id": "consumer-101", "restaurant_id": "restaurant-4",
               "items": [{"menu_item_id": "pizza", "name": "Pizza", "price": 14.0, "quantity": 1},
                         {"menu_item_id": "water", "name": "Water", "price": 2.0, "quantity": 2}],
               "reject_kitchen": reject}
    response = client.post(URLS["order"] + "/orders", json=payload)
    response.raise_for_status()
    oid = response.json()["order_id"]
    print("Created Order", oid, "reject_kitchen=", reject)
    return oid


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=["happy", "compensation", "create-only", "wait-started", "show-last"],
                        default="happy")
    args = parser.parse_args()
    with httpx.Client(timeout=5) as client:
        if args.scenario == "wait-started":
            with open("/shared/last-order-id", encoding="utf-8") as fd:
                oid = fd.read().strip()
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                response = get(client, "orchestrator", f"/sagas/{oid}")
                if response.status_code == 200 and response.json().get("step") == "AUTHORIZING":
                    print("PASS: Saga stream persisted at AUTHORIZING, before Accounting processes the command")
                    return
                time.sleep(0.4)
            raise RuntimeError("Saga did not enter AUTHORIZING before orchestrator restart")
        if args.scenario == "show-last":
            with open("/shared/last-order-id", encoding="utf-8") as fd:
                oid = fd.read().strip()
            wait_for_saga(client, oid, "COMPLETED")
            show(client, oid)
            before = get(client, "orchestrator", f"/events/{oid}").json()["events"]
            original = get(client, "order", f"/events/{oid}").json()["events"][0]["data"]
            send_duplicate(oid, original)
            time.sleep(2)
            after = get(client, "orchestrator", f"/events/{oid}").json()["events"]
            assert len(before) == len(after), "Duplicate delivery appended new saga events"
            print("PASS: duplicate OrderCreated ignored; persisted saga stream unchanged")
            print("PASS: in-flight Saga continued after orchestrator restart by replaying its stored events")
            return
        oid = create(client, reject=args.scenario == "compensation")
        if args.scenario == "create-only":
            os.makedirs("/shared", exist_ok=True)
            with open("/shared/last-order-id", "w", encoding="utf-8") as fd:
                fd.write(oid)
            print("Order created; Saga will pause at AUTHORIZING while Accounting is stopped")
            return
        expected = "COMPENSATED" if args.scenario == "compensation" else "COMPLETED"
        wait_for_saga(client, oid, expected)
        show(client, oid)
        order = get(client, "order", f"/orders/{oid}").json()
        assert order["status"] == ("CANCELLED" if args.scenario == "compensation" else "APPROVED")
        print("PASS:", expected, "; Order state", order["status"])


if __name__ == "__main__":
    main()
