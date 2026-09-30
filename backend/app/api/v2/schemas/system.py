"""Health, readiness, metadata and error-envelope schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class SolverCheck(BaseModel):
    status: Literal["ok", "unavailable"]
    solver: str = "PuLP_CBC"


class LLMCheck(BaseModel):
    provider: str
    model: str
    configured: bool


class ReadinessChecks(BaseModel):
    solver: SolverCheck
    llm: LLMCheck


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: ReadinessChecks


class MetaLimits(BaseModel):
    max_body_bytes: int
    solver_time_limit_s: int


class MetaFeatures(BaseModel):
    """Which V2 modules are live; the frontend hides what is not."""

    datasets: bool = False
    runs: bool = False
    scenarios: bool = False
    explainability: bool = False
    copilot: bool = False
    reports: bool = False


class ChangeOpInfo(BaseModel):
    op: str
    description: str
    target: Literal["one", "one_or_all", "none"] = Field(description="An entity id, an id or '*', or no target")
    params_schema: dict[str, Any] = Field(description="JSON Schema of `params`")


class MetaResponse(BaseModel):
    api_version: Literal["v2"] = "v2"
    app_version: str
    environment: str
    llm: LLMCheck
    limits: MetaLimits
    features: MetaFeatures
    objectives: list[str] = Field(default_factory=list)
    run_statuses: list[str] = Field(default_factory=list)
    change_ops: list[ChangeOpInfo] = Field(default_factory=list)
