from __future__ import annotations

import asyncio
from dataclasses import dataclass

from fastapi import HTTPException


@dataclass
class FaultState:
    delay_ms: int = 0
    fail_next: int = 0


class FaultController:
    """Small teaching-only fault injector shared by the four demo services."""

    def __init__(self) -> None:
        self.state = FaultState()
        self._lock = asyncio.Lock()

    async def before_request(self) -> None:
        async with self._lock:
            delay_ms = self.state.delay_ms
            should_fail = self.state.fail_next > 0
            if should_fail:
                self.state.fail_next -= 1

        if delay_ms > 0:
            await asyncio.sleep(delay_ms / 1000)
        if should_fail:
            raise HTTPException(status_code=503, detail="Injected transient failure")

    async def reset(self) -> dict:
        async with self._lock:
            self.state = FaultState()
        return self.snapshot()

    async def set_delay(self, delay_ms: int) -> dict:
        async with self._lock:
            self.state.delay_ms = max(0, delay_ms)
        return self.snapshot()

    async def fail_next(self, count: int) -> dict:
        async with self._lock:
            self.state.fail_next = max(0, count)
        return self.snapshot()

    def snapshot(self) -> dict:
        return {"delayMs": self.state.delay_ms, "failNext": self.state.fail_next}
