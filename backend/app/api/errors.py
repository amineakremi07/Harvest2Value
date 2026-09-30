"""Exception handlers.

Paths under /api/v2 get the error envelope; every other path (v1, /health, docs)
keeps FastAPI's default responses so v1 stays byte-for-byte unchanged.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..core.errors import AppError, error_body

logger = logging.getLogger(__name__)

V2_PREFIX = "/api/v2"

_HTTP_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    415: "UNSUPPORTED_MEDIA_TYPE",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
}


def _is_v2(request: Request) -> bool:
    return request.url.path == V2_PREFIX or request.url.path.startswith(V2_PREFIX + "/")


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _envelope(request: Request, status: int, code: str, message: str, details: dict | None = None) -> JSONResponse:
    request_id = _request_id(request)
    headers = {"X-Request-ID": request_id} if request_id else None
    return JSONResponse(error_body(code, message, details, request_id), status_code=status, headers=headers)


async def app_error_handler(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, AppError)
    return _envelope(request, exc.status, exc.code, exc.message, exc.details)


async def validation_error_handler(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, RequestValidationError)
    if not _is_v2(request):
        return await request_validation_exception_handler(request, exc)
    errors = [
        {"loc": list(err.get("loc", ())), "msg": err.get("msg", ""), "type": err.get("type", "")}
        for err in exc.errors()
    ]
    return _envelope(request, 422, "VALIDATION_ERROR", "The request is invalid.", {"errors": errors})


async def http_error_handler(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, StarletteHTTPException)
    if not _is_v2(request):
        return await http_exception_handler(request, exc)
    code = _HTTP_CODES.get(exc.status_code, "HTTP_ERROR")
    message = exc.detail if isinstance(exc.detail, str) else "Request failed."
    return _envelope(request, exc.status_code, code, message)


async def unhandled_error_handler(request: Request, exc: Exception) -> Response:
    logger.error("Unhandled error", exc_info=exc, extra={"path": request.url.path})
    if not _is_v2(request):
        # Same body as Starlette's default 500.
        return PlainTextResponse("Internal Server Error", status_code=500)
    return _envelope(
        request,
        500,
        "INTERNAL_ERROR",
        "An unexpected error occurred. Quote the request id if you report it.",
    )


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
