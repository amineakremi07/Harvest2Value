"""FastAPI dependencies shared by v2 routers."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from fastapi import Request
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from ..ai.providers import LLMProvider
from ..core.config import Settings
from ..core.errors import LLMNotConfigured
from ..core.security import RateLimiter
from ..db.session import unit_of_work
from ..optimization.engine import OptimizationEngine
from ..services.jobs import RunExecutor

T = TypeVar("T")


def get_app_settings(request: Request) -> Settings:
    """Settings the app was created with (lets tests inject their own)."""
    settings: Settings = request.app.state.settings
    return settings


def client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def rate_limit(family: str) -> Callable[[Request], None]:
    """Dependency enforcing `settings.rate_limits.<family>_per_minute` per client."""

    def _dependency(request: Request) -> None:
        settings = get_app_settings(request)
        per_minute: int = getattr(settings.rate_limits, f"{family}_per_minute")
        limiter: RateLimiter = request.app.state.rate_limiter
        limiter.hit(f"{family}:{client_key(request)}", per_minute)

    return _dependency


def get_executor(request: Request) -> RunExecutor:
    executor: RunExecutor = request.app.state.executor
    return executor


def get_engine(request: Request) -> OptimizationEngine:
    engine: OptimizationEngine = request.app.state.optimization_engine
    return engine


async def in_transaction(request: Request, work: Callable[[Session], T]) -> T:
    """Run `work` in a worker thread inside its own transaction, committed before returning.
    Async endpoints use it so that a background job started afterwards sees the committed rows."""

    def _call() -> T:
        with unit_of_work(request.app.state.session_factory) as session:
            return work(session)

    return await run_in_threadpool(_call)


def get_llm(request: Request) -> LLMProvider:
    """The app's LLM provider. Without a key the AI endpoints answer 503 LLM_NOT_CONFIGURED and
    the rest of the application keeps working."""
    settings = get_app_settings(request)
    if not settings.llm_configured:
        raise LLMNotConfigured(
            "AI features are disabled: no LLM API key is configured (set LLM_API_KEY).",
            details={"provider": settings.llm_provider},
        )
    provider: LLMProvider = request.app.state.llm_provider
    return provider
