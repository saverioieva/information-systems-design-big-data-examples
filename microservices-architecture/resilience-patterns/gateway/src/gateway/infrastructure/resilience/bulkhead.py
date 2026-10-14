from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Any, Callable, TypeVar

from gateway.application.ports.outbound.errors import BulkheadRejectedError

T = TypeVar("T")


class Bulkhead:
    """Explicit teaching implementation: dedicated capacity per dependency."""

    def __init__(
        self,
        name: str,
        max_concurrency: int = 2,
        queue_size: int = 2,
        worker_threads: int | None = None,
    ) -> None:
        self.name = name
        self.max_concurrency = max_concurrency
        self.queue_size = queue_size
        self.worker_threads = worker_threads or max_concurrency
        self._admission = threading.BoundedSemaphore(max_concurrency + queue_size)
        self._pool = ThreadPoolExecutor(
            max_workers=self.worker_threads,
            thread_name_prefix=f"bulkhead-{name}",
        )
        self._lock = threading.Lock()
        self._active = 0
        self._waiting = 0
        self._rejected = 0

    def run(
        self,
        fn: Callable[[], T],
        *,
        acquire_timeout: float = 0.02,
        exec_timeout: float | None = 2.0,
    ) -> T:
        if not self._admission.acquire(timeout=acquire_timeout):
            with self._lock:
                self._rejected += 1
            print(f"[bulkhead:{self.name}] full -> reject", flush=True)
            raise BulkheadRejectedError(f"Bulkhead '{self.name}' is full")

        with self._lock:
            self._waiting += 1

        def wrapped() -> T:
            with self._lock:
                self._waiting -= 1
                self._active += 1
            try:
                return fn()
            finally:
                with self._lock:
                    self._active -= 1

        try:
            future = self._pool.submit(wrapped)
        except Exception:
            self._admission.release()
            raise

        future.add_done_callback(lambda _future: self._admission.release())
        try:
            if exec_timeout is None:
                return future.result()
            return future.result(timeout=exec_timeout)
        except FuturesTimeout as exc:
            print(f"[bulkhead:{self.name}] execution timeout", flush=True)
            raise TimeoutError(f"Bulkhead '{self.name}' execution timed out") from exc

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "maxConcurrency": self.max_concurrency,
                "maxQueue": self.queue_size,
                "workerThreads": self.worker_threads,
                "active": self._active,
                "waiting": self._waiting,
                "rejectedTotal": self._rejected,
            }
