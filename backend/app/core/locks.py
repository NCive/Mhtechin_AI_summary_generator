"""Concurrency locks protecting AI resources (Whisper and LLM) from memory exhaustion."""
from __future__ import annotations

import asyncio

_heavy_job_lock: asyncio.Lock | None = None


def get_heavy_job_lock() -> asyncio.Lock:
    """Return the asyncio.Lock singleton bound to the current event loop."""
    global _heavy_job_lock
    if _heavy_job_lock is None:
        _heavy_job_lock = asyncio.Lock()
    return _heavy_job_lock


class _HeavyJobLockProxy:
    """Async context manager proxy ensuring the lock is acquired on the active event loop."""

    async def __aenter__(self):
        lock = get_heavy_job_lock()
        return await lock.__aenter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        lock = get_heavy_job_lock()
        return await lock.__aexit__(exc_type, exc_val, exc_tb)


HEAVY_JOB_LOCK = _HeavyJobLockProxy()
