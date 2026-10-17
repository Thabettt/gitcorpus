from __future__ import annotations

import time
from collections.abc import Callable
from typing import Protocol

from lib import cancellation


class Value(Protocol):
    value: float


class _LocalValue:
    def __init__(self, initial: float = 0.0) -> None:
        self.value = initial


def local_values() -> tuple[Value, Value, Value]:
    """Three plain slots for single-process use (tests, threads path)."""
    return _LocalValue(), _LocalValue(), _LocalValue()


def _increment(value: Value) -> float:
    lock_factory = getattr(value, "get_lock", None)
    if lock_factory is None:
        value.value += 1
        return value.value
    with lock_factory():
        value.value += 1
        return value.value


class CircuitBreaker:
    """Fleet-wide pause when consecutive transient failures cross a threshold.

    Shared across scan processes by passing ``multiprocessing`` values created
    from the same context; ``time.monotonic`` is machine-wide on supported
    platforms so a cooldown deadline written by one process gates all of them.
    """

    def __init__(
        self,
        consecutive: Value,
        trips: Value,
        cooldown_until: Value,
        *,
        trip_after: int = 5,
        base_cooldown: float = 30.0,
        max_cooldown: float = 600.0,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._consecutive = consecutive
        self._trips = trips
        self._cooldown_until = cooldown_until
        self._trip_after = trip_after
        self._base_cooldown = base_cooldown
        self._max_cooldown = max_cooldown
        self._clock = clock
        self._sleep = sleep

    def record_success(self) -> None:
        self._consecutive.value = 0
        self._trips.value = 0
        self._cooldown_until.value = 0.0

    def record_failure(self) -> None:
        count = _increment(self._consecutive)
        if count < self._trip_after:
            return
        trips = _increment(self._trips)
        cooldown = min(self._base_cooldown * (2 ** (trips - 1)), self._max_cooldown)
        self._cooldown_until.value = self._clock() + cooldown

    def wait_if_open(self) -> None:
        while True:
            remaining = self._cooldown_until.value - self._clock()
            if remaining <= 0:
                return
            cancellation.check()
            self._sleep(min(0.5, remaining))
