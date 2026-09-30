"""Rate limiting, request body size limit and CORS configuration."""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .config import Settings
from .errors import PayloadTooLarge, RateLimited, error_body
from .logging import request_id_var


@dataclass
class _Bucket:
    tokens: float
    updated: float


class RateLimiter:
    """In-memory token bucket per key. Enough for a single-process V2; swap for Redis later."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, per_minute: int) -> bool:
        capacity = float(per_minute)
        refill_per_s = per_minute / 60.0
        now = self._clock()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = self._buckets[key] = _Bucket(tokens=capacity, updated=now)
            bucket.tokens = min(capacity, bucket.tokens + (now - bucket.updated) * refill_per_s)
            bucket.updated = now
            if bucket.tokens < 1.0:
                return False
            bucket.tokens -= 1.0
            return True

    def hit(self, key: str, per_minute: int) -> None:
        if not self.allow(key, per_minute):
            raise RateLimited(details={"limit_per_minute": per_minute})


class BodySizeLimitMiddleware:
    """Reject bodies above `max_bytes`: from Content-Length up front, or while streaming."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        declared = _content_length(scope)
        if declared is not None and declared > self.max_bytes:
            await _send_json(send, 413, error_body(
                PayloadTooLarge.code,
                PayloadTooLarge.default_message,
                {"max_bytes": self.max_bytes},
                request_id_var.get(),
            ))
            return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    # FastAPI turns any other exception raised while reading the body
                    # into a 400; HTTPException is re-raised and reaches the handlers.
                    raise HTTPException(status_code=413, detail=PayloadTooLarge.default_message)
            return message

        await self.app(scope, limited_receive, send)


def _content_length(scope: Scope) -> int | None:
    for name, value in scope.get("headers", []):
        if name == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None


async def _send_json(send: Send, status: int, body: dict[str, Any]) -> None:
    payload = json.dumps(body).encode("utf-8")
    headers = [(b"content-type", b"application/json"), (b"content-length", str(len(payload)).encode())]
    request_id = request_id_var.get()
    if request_id:
        headers.append((b"x-request-id", request_id.encode()))
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": payload})


def cors_options(settings: Settings) -> dict[str, Any]:
    """Explicit allow-list; no credentials, since the API uses no cookies."""
    return {
        "allow_origins": settings.cors_origins,
        "allow_credentials": False,
        "allow_methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Accept", "If-Match", "X-Request-ID"],
        "expose_headers": ["X-Request-ID"],
        "max_age": 600,
    }
