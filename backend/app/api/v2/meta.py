"""Static information the frontend needs to adapt itself."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ...ai.providers import describe_llm
from ...core.config import Settings
from ...domain.enums import ObjectiveKind, RunStatus
from ...domain.scenario import CHANGE_TYPES
from ...scenarios.operations import OPERATIONS
from ..deps import get_app_settings
from .schemas.system import ChangeOpInfo, LLMCheck, MetaFeatures, MetaLimits, MetaResponse

router = APIRouter(tags=["meta"])


def _change_ops() -> list[ChangeOpInfo]:
    return [
        ChangeOpInfo(
            op=op,
            description=OPERATIONS[op].description,
            target=change_type.target_kind,
            params_schema=change_type.model_fields["params"].annotation.model_json_schema(),  # type: ignore[union-attr]
        )
        for op, change_type in CHANGE_TYPES.items()
    ]


@router.get("/meta", response_model=MetaResponse)
async def meta(request: Request, settings: Settings = Depends(get_app_settings)) -> MetaResponse:
    return MetaResponse(
        app_version=request.app.version,
        environment=settings.app_env,
        llm=LLMCheck(**describe_llm(settings)),
        limits=MetaLimits(
            max_body_bytes=settings.max_body_bytes,
            solver_time_limit_s=settings.solver_time_limit_s,
        ),
        features=MetaFeatures(datasets=True, runs=True, scenarios=True, explainability=True, copilot=settings.llm_configured, reports=True),
        objectives=[o.value for o in ObjectiveKind],
        run_statuses=[s.value for s in RunStatus],
        change_ops=_change_ops(),
    )
