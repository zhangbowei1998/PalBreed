"""Simple telemetry helpers."""

from __future__ import annotations

import time
from contextlib import contextmanager


@contextmanager
def timer_ms() -> int:
    start = time.perf_counter()
    result = {"elapsed_ms": 0}
    try:
        yield result
    finally:
        result["elapsed_ms"] = int((time.perf_counter() - start) * 1000)
