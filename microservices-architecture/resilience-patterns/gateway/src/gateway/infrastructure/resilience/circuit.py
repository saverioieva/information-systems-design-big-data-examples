from __future__ import annotations

import time
from typing import Any

import pybreaker

from gateway.application.ports.outbound.errors import BulkheadRejectedError, ResourceNotFoundError


class CircuitTeachingListener(pybreaker.CircuitBreakerListener):
    def __init__(self, name: str) -> None:
        self.name = name
        self.opened_at: float | None = None

    def state_change(self, cb, old_state, new_state) -> None:  # noqa: ANN001
        old_name = getattr(old_state, "name", str(old_state)).upper()
        new_name = getattr(new_state, "name", str(new_state)).upper()
        if new_name == "OPEN":
            self.opened_at = time.monotonic()
        elif new_name == "CLOSED":
            self.opened_at = None
        print(f"[circuit:{self.name}] {old_name} -> {new_name}", flush=True)

    def failure(self, cb, exc) -> None:  # noqa: ANN001
        print(f"[circuit:{self.name}] failure: {exc}", flush=True)

    def success(self, cb) -> None:  # noqa: ANN001
        print(f"[circuit:{self.name}] success", flush=True)


def build_circuit_breaker(
    name: str,
    *,
    failure_threshold: int,
    recovery_timeout_s: float,
) -> tuple[pybreaker.CircuitBreaker, CircuitTeachingListener]:
    listener = CircuitTeachingListener(name)
    breaker = pybreaker.CircuitBreaker(
        name=name,
        fail_max=failure_threshold,
        reset_timeout=recovery_timeout_s,
        exclude=[ResourceNotFoundError, BulkheadRejectedError],
        listeners=[listener],
    )
    return breaker, listener


def circuit_snapshot(
    breaker: pybreaker.CircuitBreaker,
    listener: CircuitTeachingListener,
) -> dict[str, Any]:
    remaining = 0.0
    if breaker.current_state == "open" and listener.opened_at is not None:
        elapsed = time.monotonic() - listener.opened_at
        remaining = max(0.0, float(breaker.reset_timeout) - elapsed)
    return {
        "implementation": "pybreaker",
        "state": breaker.current_state,
        "failures": breaker.fail_counter,
        "failureThreshold": breaker.fail_max,
        "recoveryTimeoutSeconds": breaker.reset_timeout,
        "recoveryRemainingSeconds": round(remaining, 2),
    }
