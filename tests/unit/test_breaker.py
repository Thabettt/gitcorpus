from __future__ import annotations

import pytest

from detect.breaker import CircuitBreaker, local_values
from lib.cancellation import RunCancelled


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def make(clock, sleeps):
    return CircuitBreaker(
        *local_values(),
        trip_after=3,
        base_cooldown=10.0,
        max_cooldown=40.0,
        clock=clock,
        sleep=sleeps.append,
    )


def test_breaker_does_not_pause_below_the_threshold():
    clock, sleeps = FakeClock(), []
    breaker = make(clock, sleeps)
    breaker.record_failure()
    breaker.record_failure()
    breaker.wait_if_open()
    assert sleeps == []


def test_breaker_trips_after_consecutive_failures_and_escalates():
    clock, sleeps = FakeClock(), []

    def advancing_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock.now += seconds

    breaker = CircuitBreaker(
        *local_values(),
        trip_after=3,
        base_cooldown=10.0,
        max_cooldown=40.0,
        clock=clock,
        sleep=advancing_sleep,
    )
    breaker.record_failure()
    breaker.record_failure()
    breaker.wait_if_open()  # below threshold: no pause
    assert sleeps == []
    breaker.record_failure()  # trips: first cooldown = 10s
    breaker.wait_if_open()
    assert abs(sum(sleeps) - 10.0) < 0.6
    before_escalation = len(sleeps)
    breaker.record_failure()  # 4th consecutive: escalate to 20s
    breaker.wait_if_open()
    assert abs(sum(sleeps[before_escalation:]) - 20.0) < 1.2


def test_breaker_success_resets_everything():
    clock, sleeps = FakeClock(), []
    breaker = make(clock, sleeps)
    breaker.record_failure()
    breaker.record_failure()
    breaker.record_success()
    breaker.record_failure()
    breaker.wait_if_open()
    assert sleeps == []


def test_breaker_wait_is_interruptible_by_cancellation():
    from lib import cancellation

    clock, sleeps = FakeClock(), []
    breaker = make(clock, sleeps)
    for _ in range(3):
        breaker.record_failure()
    token = cancellation.bind(lambda: True)
    try:
        with pytest.raises(RunCancelled):
            breaker.wait_if_open()
    finally:
        cancellation.reset(token)


def test_breaker_wait_sleeps_until_the_cooldown_expires():
    clock, sleeps = FakeClock(), []

    def advancing_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock.now += seconds

    breaker = CircuitBreaker(
        *local_values(), trip_after=1, base_cooldown=5.0, clock=clock, sleep=advancing_sleep
    )
    breaker.record_failure()
    breaker.wait_if_open()
    assert clock.now >= 1005.0
    assert sleeps  # it actually waited
