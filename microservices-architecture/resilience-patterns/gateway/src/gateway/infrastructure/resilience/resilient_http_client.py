from __future__ import annotations

import asyncio
from typing import Any

import pybreaker
import requests
from tenacity import Retrying, RetryCallState, retry_if_exception_type, stop_after_attempt, wait_exponential

from gateway.application.ports.outbound.errors import (
    BulkheadRejectedError,
    CircuitOpenError,
    ResourceNotFoundError,
    TransientCallError,
)
from gateway.infrastructure.resilience.bulkhead import Bulkhead
from gateway.infrastructure.resilience.circuit import build_circuit_breaker, circuit_snapshot


class ResilientHttpClient:
    """HTTP infrastructure used by one outbound adapter.

    Bulkhead -> Circuit Breaker (PyBreaker) -> Retry (Tenacity) -> requests timeout.

    The bulkhead admission is intentionally outside PyBreaker. PyBreaker protects
    its full call with an internal lock; placing the bulkhead inside the breaker
    would serialize callers before they can contend for bulkhead capacity, making
    the Bulkhead demo unable to saturate.
    """

    def __init__(
        self,
        name: str,
        base_url: str,
        *,
        timeout_s: float,
        max_attempts: int,
        initial_backoff_s: float,
        max_backoff_s: float,
        failure_threshold: int,
        recovery_timeout_s: float,
        max_concurrency: int,
        max_queue: int,
    ) -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.max_attempts = max_attempts
        self.bulkhead = Bulkhead(
            name=name,
            max_concurrency=max_concurrency,
            queue_size=max_queue,
            worker_threads=max_concurrency,
        )
        self.circuit, self._listener = build_circuit_breaker(
            name,
            failure_threshold=failure_threshold,
            recovery_timeout_s=recovery_timeout_s,
        )
        self._retrying = Retrying(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(
                multiplier=initial_backoff_s,
                min=initial_backoff_s,
                max=max_backoff_s,
            ),
            retry=retry_if_exception_type((TransientCallError, TimeoutError)),
            before=self._before_attempt,
            before_sleep=self._before_sleep,
            reraise=True,
        )

    async def get_json(self, path: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._get_json_sync, path)

    def _get_json_sync(self, path: str) -> dict[str, Any]:
        # Admit/reject the complete logical dependency call before entering
        # PyBreaker. This keeps the per-dependency capacity boundary observable
        # even though PyBreaker serializes its protected call internally.
        return self.bulkhead.run(
            lambda: self._circuit_then_retry(path),
            acquire_timeout=0.02,
            exec_timeout=None,
        )

    def _circuit_then_retry(self, path: str) -> dict[str, Any]:
        def retried_operation() -> dict[str, Any]:
            return self._retrying(self._one_attempt, path)

        try:
            return self.circuit.call(retried_operation)
        except pybreaker.CircuitBreakerError as exc:
            print(f"[circuit:{self.name}] OPEN -> fail fast", flush=True)
            raise CircuitOpenError(f"Circuit '{self.name}' is open") from exc

    def _one_attempt(self, path: str) -> dict[str, Any]:
        # HTTP timeout bounds each individual retry attempt.
        return self._http_get(path)

    def _http_get(self, path: str) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            response = requests.get(url, timeout=self.timeout_s)
        except requests.RequestException as exc:
            raise TransientCallError(f"{self.name}: transport failure: {exc}") from exc

        if response.status_code == 404:
            raise ResourceNotFoundError(f"{self.name}: resource not found")
        if response.status_code >= 500:
            raise TransientCallError(f"{self.name}: HTTP {response.status_code}")
        try:
            response.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f"{self.name}: HTTP {response.status_code}") from exc
        return response.json()

    def _before_attempt(self, retry_state: RetryCallState) -> None:
        print(
            f"[retry:{self.name}] attempt {retry_state.attempt_number}/{self.max_attempts}",
            flush=True,
        )

    def _before_sleep(self, retry_state: RetryCallState) -> None:
        sleep = retry_state.next_action.sleep if retry_state.next_action else 0
        print(
            f"[retry:{self.name}] transient failure -> wait {sleep:.2f}s",
            flush=True,
        )

    def snapshot(self) -> dict[str, Any]:
        return {
            "circuitBreaker": circuit_snapshot(self.circuit, self._listener),
            "retry": {
                "implementation": "tenacity",
                "maxAttempts": self.max_attempts,
            },
            "bulkhead": self.bulkhead.snapshot(),
            "timeoutSeconds": self.timeout_s,
        }
