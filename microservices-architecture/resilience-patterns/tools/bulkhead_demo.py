from __future__ import annotations

import concurrent.futures
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://gateway:8000").rstrip("/")
KITCHEN_ADMIN_URL = os.getenv("KITCHEN_ADMIN_URL", "http://kitchen-service:8002").rstrip("/")
REQUESTS = int(os.getenv("REQUESTS", "12"))
WORKERS = int(os.getenv("WORKERS", "12"))
KITCHEN_DELAY_MS = int(os.getenv("KITCHEN_DELAY_MS", "600"))
ORDER_ID = os.getenv("ORDER_ID", "1001")


def request_json(
    url: str,
    *,
    method: str = "GET",
    timeout: float = 10.0,
) -> tuple[int, dict[str, Any] | None, float]:
    started = time.perf_counter()
    request = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read()
            data = json.loads(payload) if payload else None
            return response.status, data, time.perf_counter() - started
    except urllib.error.HTTPError as exc:
        payload = exc.read()
        data = json.loads(payload) if payload else None
        return exc.code, data, time.perf_counter() - started


def gateway(path: str, *, timeout: float = 10.0) -> tuple[int, dict[str, Any] | None, float]:
    return request_json(f"{GATEWAY_URL}{path}", timeout=timeout)


def kitchen_admin(path: str) -> tuple[int, dict[str, Any] | None, float]:
    return request_json(f"{KITCHEN_ADMIN_URL}{path}", method="POST")


def wait_until_ready() -> None:
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        gateway_status, _, _ = gateway("/health", timeout=1.0)
        kitchen_status, _, _ = request_json(f"{KITCHEN_ADMIN_URL}/health", timeout=1.0)
        if gateway_status == 200 and kitchen_status == 200:
            return
        time.sleep(0.5)
    raise RuntimeError("Gateway or Kitchen Service did not become ready within 30 seconds")


def resilience_snapshot() -> dict[str, Any]:
    status, payload, _ = gateway("/resilience")
    if status != 200 or payload is None:
        raise RuntimeError(f"Cannot read /resilience: HTTP {status}")
    return payload


def ensure_kitchen_circuit_closed() -> None:
    kitchen_admin("/admin/reset")
    snapshot = resilience_snapshot()["kitchen"]["circuitBreaker"]
    if snapshot["state"] == "open":
        wait_s = float(snapshot.get("recoveryRemainingSeconds", 0.0)) + 0.25
        print(f"Kitchen circuit is OPEN; waiting {wait_s:.2f}s for HALF_OPEN trial...")
        time.sleep(wait_s)

    status, payload, _ = gateway(f"/diagnostics/dependencies/kitchen/{ORDER_ID}")
    if status != 200:
        raise RuntimeError(
            "Kitchen diagnostic probe could not establish a healthy CLOSED circuit: "
            f"HTTP {status} {payload}"
        )


def kitchen_call(_: int) -> tuple[int, float]:
    status, _, elapsed = gateway(
        f"/diagnostics/dependencies/kitchen/{ORDER_ID}",
        timeout=15.0,
    )
    return status, elapsed


def print_summary(
    kitchen_results: list[tuple[int, float]],
    probes: dict[str, tuple[int, float]],
    rejected_delta: int,
) -> bool:
    succeeded = sum(1 for status, _ in kitchen_results if status == 200)
    rejected = sum(1 for status, _ in kitchen_results if status == 429)
    other = REQUESTS - succeeded - rejected
    probes_ok = all(status == 200 for status, _ in probes.values())
    isolated = rejected > 0 and probes_ok

    print("\nBulkhead isolation demo")
    print("-----------------------")
    print(f"Kitchen delay:       {KITCHEN_DELAY_MS} ms")
    print(f"Kitchen requests:    {REQUESTS}")
    print(f"Kitchen succeeded:   {succeeded}")
    print(f"Kitchen rejected:    {rejected} (HTTP 429)")
    print(f"Other Kitchen status:{other}")
    print(f"Rejected counter +:  {rejected_delta}")

    print("\nProbes while Kitchen is busy")
    print("----------------------------")
    for name, (status, elapsed) in probes.items():
        print(f"{name.capitalize():<10} HTTP {status:<3} {elapsed * 1000:7.1f} ms")

    print("\nResult")
    print("------")
    if isolated:
        print("PASS: Kitchen saturation stayed inside the Kitchen bulkhead.")
        print("Order, Delivery, and Payment kept their independent capacity.")
    else:
        print("FAIL: the expected bulkhead isolation was not observed.")

    return isolated


def main() -> int:
    print("Preparing reproducible Bulkhead demo...")
    wait_until_ready()
    ensure_kitchen_circuit_closed()

    kitchen_bulkhead = resilience_snapshot()["kitchen"]["bulkhead"]
    before = kitchen_bulkhead["rejectedTotal"]
    print(
        "Kitchen bulkhead: "
        f"maxConcurrency={kitchen_bulkhead['maxConcurrency']}, "
        f"maxQueue={kitchen_bulkhead['maxQueue']}"
    )

    status, _, _ = kitchen_admin(f"/admin/delay/{KITCHEN_DELAY_MS}")
    if status != 200:
        raise RuntimeError(f"Cannot configure Kitchen delay: HTTP {status}")

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
            kitchen_futures = [pool.submit(kitchen_call, i) for i in range(REQUESTS)]

            # Let the Kitchen calls occupy its dedicated workers and queue.
            time.sleep(0.15)
            probes = {}
            for service in ("order", "delivery", "payment"):
                probe_status, _, elapsed = gateway(
                    f"/diagnostics/dependencies/{service}/{ORDER_ID}"
                )
                probes[service] = (probe_status, elapsed)

            kitchen_results = [future.result() for future in kitchen_futures]

        after = resilience_snapshot()["kitchen"]["bulkhead"]["rejectedTotal"]
        return 0 if print_summary(kitchen_results, probes, after - before) else 1
    finally:
        kitchen_admin("/admin/reset")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        try:
            kitchen_admin("/admin/reset")
        except Exception:
            pass
        raise SystemExit(2)
