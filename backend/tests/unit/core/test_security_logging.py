import json
import logging

import pytest

from app.core.errors import RateLimited
from app.core.logging import JsonFormatter, request_id_var
from app.core.security import RateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_rate_limiter_allows_burst_then_blocks_then_refills() -> None:
    clock = FakeClock()
    limiter = RateLimiter(clock=clock)

    assert all(limiter.allow("k", per_minute=3) for _ in range(3))
    assert not limiter.allow("k", per_minute=3)

    clock.now += 20  # 3/min -> one token every 20 s
    assert limiter.allow("k", per_minute=3)
    assert not limiter.allow("k", per_minute=3)


def test_rate_limiter_keys_are_independent() -> None:
    limiter = RateLimiter(clock=FakeClock())
    assert limiter.allow("a", per_minute=1)
    assert limiter.allow("b", per_minute=1)
    assert not limiter.allow("a", per_minute=1)


def test_hit_raises_rate_limited() -> None:
    limiter = RateLimiter(clock=FakeClock())
    limiter.hit("k", per_minute=1)
    with pytest.raises(RateLimited) as exc:
        limiter.hit("k", per_minute=1)
    assert exc.value.status == 429 and exc.value.details == {"limit_per_minute": 1}


def test_json_log_line_carries_request_id_and_extras() -> None:
    token = request_id_var.set("req-123")
    try:
        record = logging.makeLogRecord({"name": "app.test", "levelname": "INFO", "msg": "hello %s", "args": ("world",)})
        record.provider = "groq"
        line = json.loads(JsonFormatter().format(record))
    finally:
        request_id_var.reset(token)

    assert line["message"] == "hello world"
    assert line["request_id"] == "req-123"
    assert line["provider"] == "groq"
