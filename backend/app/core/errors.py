"""Application errors with a stable code, an HTTP status and safe, user-facing details."""

from __future__ import annotations

from typing import Any


def error_body(
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """The single error envelope returned by every /api/v2 failure."""
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "request_id": request_id,
        }
    }


class AppError(Exception):
    code = "APP_ERROR"
    status = 400
    default_message = "The request could not be processed."

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
        code: str | None = None,
        status: int | None = None,
    ) -> None:
        self.message = message or self.default_message
        self.details = details or {}
        if code is not None:
            self.code = code
        if status is not None:
            self.status = status
        super().__init__(self.message)


class NotFound(AppError):
    code = "NOT_FOUND"
    status = 404
    default_message = "Resource not found."


class Conflict(AppError):
    code = "CONFLICT"
    status = 409
    default_message = "The request conflicts with the current state of the resource."


class ValidationFailed(AppError):
    code = "VALIDATION_ERROR"
    status = 422
    default_message = "The request is invalid."


class RateLimited(AppError):
    code = "RATE_LIMITED"
    status = 429
    default_message = "Too many requests. Please retry later."


class PayloadTooLarge(AppError):
    code = "PAYLOAD_TOO_LARGE"
    status = 413
    default_message = "The request body is too large."


class LLMNotConfigured(AppError):
    code = "LLM_NOT_CONFIGURED"
    status = 503
    default_message = "The AI service is not configured."


class LLMUpstreamError(AppError):
    code = "LLM_UPSTREAM_ERROR"
    status = 502
    default_message = "The AI service returned an unusable response."


class LLMTimeout(AppError):
    code = "LLM_TIMEOUT"
    status = 504
    default_message = "The AI service did not answer in time."


class SolverBusy(AppError):
    code = "SOLVER_BUSY"
    status = 503
    default_message = "The optimization queue is full. Please retry later."


class ScenarioApplyError(AppError):
    code = "SCENARIO_APPLY_ERROR"
    status = 422
    default_message = "The scenario changes could not be applied."
