import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor

import pybreaker
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_fixed

from gateway.application.ports.outbound.errors import BulkheadRejectedError, TransientCallError
from gateway.infrastructure.resilience.bulkhead import Bulkhead
from gateway.infrastructure.resilience.circuit import build_circuit_breaker
from gateway.infrastructure.resilience.resilient_http_client import ResilientHttpClient


class RetryTests(unittest.TestCase):
    def test_tenacity_succeeds_on_third_attempt(self):
        attempts = 0
        retrying = Retrying(
            stop=stop_after_attempt(3),
            wait=wait_fixed(0),
            retry=retry_if_exception_type(TransientCallError),
            reraise=True,
        )

        def operation():
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise TransientCallError("temporary")
            return "ok"

        self.assertEqual("ok", retrying(operation))
        self.assertEqual(3, attempts)


class CircuitBreakerTests(unittest.TestCase):
    def test_pybreaker_opens_and_fails_fast(self):
        breaker, _listener = build_circuit_breaker(
            "test",
            failure_threshold=2,
            recovery_timeout_s=60,
        )

        def fail():
            raise TransientCallError("down")

        with self.assertRaises(TransientCallError):
            breaker.call(fail)
        with self.assertRaises(pybreaker.CircuitBreakerError):
            breaker.call(fail)

        self.assertEqual("open", breaker.current_state)
        with self.assertRaises(pybreaker.CircuitBreakerError):
            breaker.call(fail)

    def test_half_open_success_closes(self):
        breaker, _listener = build_circuit_breaker(
            "test",
            failure_threshold=1,
            recovery_timeout_s=0.01,
        )

        def fail():
            raise TransientCallError("down")

        with self.assertRaises(pybreaker.CircuitBreakerError):
            breaker.call(fail)

        time.sleep(0.02)
        self.assertEqual("ok", breaker.call(lambda: "ok"))
        self.assertEqual("closed", breaker.current_state)


class BulkheadTests(unittest.TestCase):
    def test_rejects_when_execution_and_queue_are_full(self):
        bulkhead = Bulkhead("test", max_concurrency=1, queue_size=1, worker_threads=1)
        gate = threading.Event()

        def slow():
            gate.wait(timeout=2)
            return "ok"

        callers = ThreadPoolExecutor(max_workers=3)
        first = callers.submit(bulkhead.run, slow, acquire_timeout=0.1, exec_timeout=2)
        time.sleep(0.05)
        second = callers.submit(bulkhead.run, slow, acquire_timeout=0.1, exec_timeout=2)
        time.sleep(0.05)

        with self.assertRaises(BulkheadRejectedError):
            bulkhead.run(slow, acquire_timeout=0.01, exec_timeout=2)

        gate.set()
        self.assertEqual("ok", first.result(timeout=2))
        self.assertEqual("ok", second.result(timeout=2))
        callers.shutdown(wait=True)


class ResilientClientBulkheadIntegrationTests(unittest.TestCase):
    def test_concurrent_calls_reach_bulkhead_before_pybreaker_serialization(self):
        client = ResilientHttpClient(
            "test",
            "http://unused",
            timeout_s=1.0,
            max_attempts=1,
            initial_backoff_s=0.01,
            max_backoff_s=0.01,
            failure_threshold=20,
            recovery_timeout_s=60,
            max_concurrency=2,
            max_queue=2,
        )

        def slow_http(_path):
            time.sleep(0.15)
            return {"ok": True}

        client._http_get = slow_http  # teaching regression test: no real network

        def call():
            try:
                client._get_json_sync("/test")
                return "ok"
            except BulkheadRejectedError:
                return "rejected"

        with ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(lambda _i: call(), range(12)))

        self.assertEqual(4, results.count("ok"))
        self.assertEqual(8, results.count("rejected"))



if __name__ == "__main__":
    unittest.main()
