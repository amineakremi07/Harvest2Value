"""JSON logging with a per-request id carried by a context variable."""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .ids import new_id

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

APP_LOGGER = "app"

# Attributes every LogRecord has; anything else was passed through `extra=`.
_STANDARD_ATTRS = frozenset(vars(logging.makeLogRecord({}))) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        for key, value in vars(record).items():
            if key not in _STANDARD_ATTRS and not key.startswith("_"):
                entry[key] = value
        if record.exc_info:
            entry["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str, ensure_ascii=False)


_REQUEST_ID_HEADER = b"x-request-id"
_MAX_REQUEST_ID_LEN = 64


def _accept_request_id(raw: bytes) -> str | None:
    """Reuse a caller-supplied id only if it is short and made of safe characters."""
    try:
        value = raw.decode("ascii")
    except UnicodeDecodeError:
        return None
    if 0 < len(value) <= _MAX_REQUEST_ID_LEN and all(c.isalnum() or c in "-_." for c in value):
        return value
    return None


class RequestIdMiddleware:
    """Assign a request id (or reuse X-Request-ID), expose it to logs and echo it back."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = next((v for k, v in scope.get("headers", []) if k == _REQUEST_ID_HEADER), b"")
        request_id = _accept_request_id(incoming) or new_id()
        request_id_var.set(request_id)
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = [(k, v) for k, v in message.get("headers", []) if k != _REQUEST_ID_HEADER]
                headers.append((_REQUEST_ID_HEADER, request_id.encode("ascii")))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_id)


def configure_logging(level: str = "INFO") -> None:
    """Route the `app.*` loggers to a single JSON handler on stderr. Idempotent."""
    logger = logging.getLogger(APP_LOGGER)
    logger.setLevel(level)
    if not any(getattr(h, "_h2v_json", False) for h in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        handler._h2v_json = True  # type: ignore[attr-defined]
        logger.addHandler(handler)
    logger.propagate = False
