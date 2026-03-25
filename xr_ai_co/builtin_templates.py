"""Deterministic artifacts for demo missions (no LLM)."""

RATE_LIMIT_MODULE = '''\
"""Token bucket rate limiter (MVP demo)."""


class TokenBucket:
    def __init__(self, rate: float, capacity: float) -> None:
        if rate <= 0 or capacity <= 0:
            raise ValueError("rate and capacity must be positive")
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity

    def consume(self, n: float = 1.0) -> bool:
        if n <= 0:
            return True
        if n > self.capacity:
            return False
        if self.tokens >= n:
            self.tokens -= n
            return True
        return False

    def refill(self, elapsed: float) -> None:
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
'''

RATE_LIMIT_TEST = '''\
import pytest

from ratelimit import TokenBucket


def test_consume_basic():
    b = TokenBucket(rate=10.0, capacity=2.0)
    assert b.consume(1) is True
    assert b.consume(1) is True
    assert b.consume(1) is False


def test_refill():
    b = TokenBucket(rate=10.0, capacity=2.0)
    assert b.consume(2) is True
    assert b.consume(1) is False
    b.refill(0.5)
    assert b.consume(1) is True


def test_invalid_ctor():
    with pytest.raises(ValueError):
        TokenBucket(rate=0, capacity=1)
    with pytest.raises(ValueError):
        TokenBucket(rate=1, capacity=0)
'''

# Flat app.py — matches common LLM tests (import app; app.hello_world / app.main).
GENERIC_MAIN = '''\
"""Minimal app module for generic stub missions."""


def hello_world() -> str:
    return "Hello, World!"


def main() -> None:
    print(hello_world())
'''

GENERIC_TEST = '''\
import app


def test_hello_world():
    assert app.hello_world() == "Hello, World!"


def test_main_exists():
    assert callable(app.main)
'''
