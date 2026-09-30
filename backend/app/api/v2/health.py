"""Liveness and readiness."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pulp import PULP_CBC_CMD
from starlette.concurrency import run_in_threadpool

from ...ai.providers import describe_llm
from ...core.config import Settings
from ..deps import get_app_settings
from .schemas.system import HealthResponse, LLMCheck, ReadinessChecks, ReadinessResponse, SolverCheck

router = APIRouter(tags=["health"])


def _cbc_available() -> bool:
    return bool(PULP_CBC_CMD(msg=False).available())


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    responses={503: {"model": ReadinessResponse, "description": "A required component is unavailable"}},
)
async def ready(settings: Settings = Depends(get_app_settings)) -> JSONResponse:
    solver_ok = await run_in_threadpool(_cbc_available)
    # A missing LLM key is reported but not blocking: the app works without AI.
    body = ReadinessResponse(
        status="ready" if solver_ok else "not_ready",
        checks=ReadinessChecks(
            solver=SolverCheck(status="ok" if solver_ok else "unavailable"),
            llm=LLMCheck(**describe_llm(settings)),
        ),
    )
    return JSONResponse(body.model_dump(), status_code=200 if solver_ok else 503)
