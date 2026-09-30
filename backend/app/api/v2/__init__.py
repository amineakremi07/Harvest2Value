"""API v2 router: every v2 endpoint is mounted under /api/v2."""

from fastapi import APIRouter

from . import analytics, comparisons, datasets, explain, health, insights, meta, runs, scenarios

router = APIRouter(prefix="/api/v2")
router.include_router(health.router)
router.include_router(meta.router)
router.include_router(datasets.router)
router.include_router(runs.router)
router.include_router(explain.router)
router.include_router(insights.router)
router.include_router(analytics.router)
router.include_router(scenarios.router)
router.include_router(comparisons.router)
