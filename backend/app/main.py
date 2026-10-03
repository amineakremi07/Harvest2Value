"""Harvest2Value FastAPI application entry point."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from .ai.providers import get_provider
from .api.errors import install_error_handlers
from .api.v2 import router as v2_router
from .core.config import Settings, get_settings
from .core.logging import RequestIdMiddleware, configure_logging
from .core.security import BodySizeLimitMiddleware, RateLimiter, cors_options
from .db.engine import make_engine, make_session_factory
from .db.session import ensure_default_workspace, unit_of_work, upgrade_database
from .optimization.engine import OptimizationEngine
from .optimization.runner import SolverRunner
from .routers import chat, explain, optimize, scenario
from .services.jobs import RunExecutor
from .services.optimization import OptimizationService


logger = logging.getLogger(__name__)


def _init_database(app: FastAPI, settings: Settings) -> None:
    engine = make_engine(settings.database_url)
    upgrade_database(engine, settings.database_url)
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    ensure_default_workspace(app.state.session_factory)
    # Jobs live in memory: runs a previous process left queued/running will never finish.
    with unit_of_work(app.state.session_factory) as session:
        interrupted = OptimizationService(session).recover_interrupted()
    if interrupted:
        logger.warning("Marked unfinished runs as interrupted", extra={"count": interrupted})


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # The database is only needed by /api/v2; v1 keeps working without it.
    await run_in_threadpool(_init_database, app, app.state.settings)
    settings: Settings = app.state.settings
    app.state.optimization_engine = OptimizationEngine(
        runner=SolverRunner(max_concurrency=settings.solver_max_concurrency),
        default_time_limit_s=settings.solver_time_limit_s,
    )
    app.state.executor = RunExecutor(max_concurrency=settings.solver_max_concurrency)
    try:
        yield
    finally:
        await app.state.executor.shutdown()
        app.state.engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging()

    app = FastAPI(title="Harvest2Value API", version="2.0.0-dev", lifespan=lifespan)
    app.state.settings = settings
    app.state.rate_limiter = RateLimiter()
    app.state.llm_provider = get_provider(settings)  # tests replace it with a scripted MockProvider

    # Last added runs first: request id -> CORS -> body size limit -> app.
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_body_bytes)
    app.add_middleware(CORSMiddleware, **cors_options(settings))
    app.add_middleware(RequestIdMiddleware)

    install_error_handlers(app)

    # API v1 — unchanged until Phase 14.
    app.include_router(optimize.router)
    app.include_router(scenario.router)
    app.include_router(explain.router)
    app.include_router(chat.router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "healthy", "service": "Harvest2Value"}

    app.include_router(v2_router)
    return app


app = create_app()
