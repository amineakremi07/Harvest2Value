"""AI endpoints (plan §8 — copilot): conversations, messages (JSON or SSE), action confirm/reject,
tool catalogue, narratives and free text -> scenario changes.

Without an LLM key every endpoint that needs the model answers 503 LLM_NOT_CONFIGURED; reading
conversations, rejecting actions and confirming already-proposed actions keep working.
"""

from __future__ import annotations

import json
import logging
from functools import partial
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ...ai.copilot import Copilot, TurnResult
from ...ai.narratives import comparison_narrative, run_narrative
from ...ai.providers import LLMProvider
from ...ai.tools.registry import registry
from ...core.errors import AppError
from ...db.models import DEFAULT_WORKSPACE_ID, Message
from ...db.session import get_session
from ...domain.report import ReportSpec
from ...scenarios.parse import ParseRequest, ParseResult, parse_scenario_text
from ...services.copilot import CopilotService
from ...services.optimization import execute_run
from ..deps import get_app_settings, get_engine, get_executor, get_llm, in_transaction, rate_limit
from .reports import report_narrative
from .schemas.common import Page
from .schemas.copilot import (
    ActionView,
    ComparisonNarrativeRequest,
    ConversationCreate,
    ConversationDetail,
    ConversationSummary,
    MessageCreate,
    MessageView,
    NarrativeRequest,
    NarrativeResponse,
    ToolInfo,
    ToolsResponse,
    TurnResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["copilot"])

PageNo = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]
LLM_ERRORS = {
    429: {"description": "RATE_LIMITED"},
    502: {"description": "LLM_UPSTREAM_ERROR"},
    503: {"description": "LLM_NOT_CONFIGURED: AI disabled"},
    504: {"description": "LLM_TIMEOUT"},
}


def get_service(session: Session = Depends(get_session, scope="function")) -> CopilotService:
    return CopilotService(session)


Service = Annotated[CopilotService, Depends(get_service)]
LLM = Annotated[LLMProvider, Depends(get_llm)]


def _detail(service: CopilotService, conversation_id: str) -> ConversationDetail:
    conversation = service.get(conversation_id)
    return ConversationDetail(
        **ConversationSummary.of(conversation).model_dump(),
        context=conversation.context,
        messages=[MessageView.of(m) for m in service.messages(conversation.id)],
        actions=[ActionView.of(a) for a in service.actions_of(conversation.id)],
    )


# ---- conversations ------------------------------------------------------------------------------


@router.post("/copilot/conversations", response_model=ConversationDetail, status_code=status.HTTP_201_CREATED)
def create_conversation(service: Service, body: ConversationCreate | None = None) -> ConversationDetail:
    body = body or ConversationCreate()
    conversation = service.create(title=body.title, context=body.context)
    return _detail(service, conversation.id)


@router.get("/copilot/conversations", response_model=Page[ConversationSummary])
def list_conversations(service: Service, page: PageNo = 1, page_size: PageSize = 20) -> Page[ConversationSummary]:
    rows, total = service.list(page=page, page_size=page_size)
    return Page(items=[ConversationSummary.of(r) for r in rows], total=total, page=page, page_size=page_size)


@router.get("/copilot/conversations/{conversation_id}", response_model=ConversationDetail, responses={404: {"description": "Not found"}})
def get_conversation(conversation_id: str, service: Service) -> ConversationDetail:
    return _detail(service, conversation_id)


@router.delete("/copilot/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT, responses={404: {"description": "Not found"}})
def delete_conversation(conversation_id: str, service: Service) -> Response:
    service.delete(conversation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---- messages -----------------------------------------------------------------------------------


def _sse(event: str, data: Any) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n".encode("utf-8")


def _wants_stream(request: Request, stream: bool | None) -> bool:
    if stream is not None:
        return stream
    return "text/event-stream" in request.headers.get("accept", "")


@router.post(
    "/copilot/conversations/{conversation_id}/messages",
    response_model=TurnResponse,
    responses={
        200: {"content": {"text/event-stream": {}}, "description": "JSON, or SSE with `stream=true` / Accept: text/event-stream"},
        404: {"description": "Conversation not found"},
        **LLM_ERRORS,
    },
    dependencies=[Depends(rate_limit("copilot"))],
)
async def post_message(
    conversation_id: str,
    body: MessageCreate,
    request: Request,
    provider: LLM,
    stream: bool | None = None,
) -> Any:
    """One copilot turn. SSE events: `user_message`, `tool_call`, `tool_result`, `answer`
    (final message + proposed actions) or `error`, then `done`. Numbers in the answer are rendered
    by the backend from tool results; anything unverified is marked ⟦?…⟧. Proposals are only
    *pending* actions: nothing changes until POST /copilot/actions/{id}/confirm."""
    prepared = await in_transaction(request, lambda s: CopilotService(s).prepare_turn(conversation_id, body.content, body.context))
    user_message = await in_transaction(request, lambda s: MessageView.of(_message(s, prepared.user_message_id)))
    copilot = Copilot(provider, request.app.state.session_factory)
    holder: list[TurnResult] = []

    async def finish() -> TurnResponse:
        result = holder[0]
        message, actions = await in_transaction(
            request,
            lambda s: _views(CopilotService(s).save_turn(conversation_id, prepared.state, result)),
        )
        return TurnResponse(user_message=user_message, message=message, actions=actions)

    async def fail(exc: AppError) -> MessageView:
        return await in_transaction(request, lambda s: MessageView.of(CopilotService(s).save_error(conversation_id, exc.message)))

    if not _wants_stream(request, stream):
        try:
            async for _event in copilot.run_turn(prepared.state, prepared.history, on_result=holder.append):
                pass
        except AppError as exc:
            await fail(exc)
            raise
        return await finish()

    async def events() -> AsyncIterator[bytes]:
        yield _sse("user_message", user_message.model_dump(mode="json"))
        try:
            async for event in copilot.run_turn(prepared.state, prepared.history, on_result=holder.append):
                if event.event in ("tool_call", "tool_result"):
                    yield _sse(event.event, event.data)
            turn = await finish()
            yield _sse("answer", {"message": turn.message.model_dump(mode="json"), "actions": [a.model_dump(mode="json") for a in turn.actions]})
        except AppError as exc:
            error = await fail(exc)
            yield _sse("error", {"code": exc.code, "message": exc.message, "message_view": error.model_dump(mode="json")})
        except Exception:  # noqa: BLE001 - never leak internals into the stream
            logger.exception("Copilot turn failed")
            yield _sse("error", {"code": "INTERNAL_ERROR", "message": "The copilot failed. Please retry."})
        yield _sse("done", {})

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _message(session: Session, message_id: str) -> Message:
    message = session.get(Message, message_id)
    assert message is not None
    return message


def _views(saved: tuple[Any, list[Any]]) -> tuple[MessageView, list[ActionView]]:
    message, actions = saved
    return MessageView.of(message), [ActionView.of(a) for a in actions]


# ---- actions ------------------------------------------------------------------------------------


@router.post(
    "/copilot/actions/{action_id}/confirm",
    response_model=ActionView,
    responses={404: {"description": "Action not found"}, 409: {"description": "ACTION_EXPIRED or ACTION_ALREADY_DECIDED"}},
)
async def confirm_action(action_id: str, request: Request) -> ActionView:
    """Executes a pending proposal exactly once (idempotent: confirming again returns the same
    result). A proposed run is queued like POST /runs."""
    action = await in_transaction(request, lambda s: ActionView.of(CopilotService(s).get_action(action_id)))
    narrative = None
    if action.kind == "generate_report" and action.status == "pending":
        narrative = await report_narrative(request, ReportSpec.model_validate(action.payload))
    if action.kind == "run_optimization" and action.status == "pending":
        get_executor(request).ensure_capacity()
    outcome = await in_transaction(request, lambda s: _confirm(s, action_id, narrative))
    view, created = outcome
    if created is not None and not created.cache_hit:
        executor = get_executor(request)
        executor.submit(created.run.id, _job(request, created.run.id))
    return view


def _confirm(session: Session, action_id: str, narrative: dict[str, Any] | None) -> tuple[ActionView, Any]:
    outcome = CopilotService(session).confirm(action_id, narrative)
    return ActionView.of(outcome.action), outcome.created_run


def _job(request: Request, run_id: str) -> Any:
    return partial(execute_run, request.app.state.session_factory, get_engine(request), run_id)


@router.post(
    "/copilot/actions/{action_id}/reject",
    response_model=ActionView,
    responses={404: {"description": "Action not found"}, 409: {"description": "ACTION_EXPIRED or ACTION_ALREADY_DECIDED"}},
)
def reject_action(action_id: str, service: Service) -> ActionView:
    return ActionView.of(service.reject(action_id))


@router.get("/copilot/tools", response_model=ToolsResponse)
def list_tools(request: Request) -> ToolsResponse:
    """The tools the model may call. There is no shell, file, network or configuration tool."""
    tools = [ToolInfo(name=t.name, description=t.description, kind=t.kind, parameters=t.spec().parameters) for t in registry().values()]
    return ToolsResponse(tools=tools, llm_configured=get_app_settings(request).llm_configured)


# ---- AI text ------------------------------------------------------------------------------------


@router.post(
    "/runs/{run_id}/explanation/narrative",
    response_model=NarrativeResponse,
    responses={404: {"description": "Run not found"}, 409: {"description": "Run has no plan"}, **LLM_ERRORS},
    dependencies=[Depends(rate_limit("narrative"))],
)
async def explanation_narrative(run_id: str, request: Request, provider: LLM, body: NarrativeRequest | None = None) -> NarrativeResponse:
    body = body or NarrativeRequest()
    out = await run_narrative(provider, request.app.state.session_factory, DEFAULT_WORKSPACE_ID, run_id, body.locale)
    return NarrativeResponse(text=out.text, verification=out.verification, locale=out.locale, model=out.model, prompt=out.prompt)


@router.post(
    "/comparisons/narrative",
    response_model=NarrativeResponse,
    responses={404: {"description": "Run not found"}, 422: {"description": "INCOMPARABLE"}, **LLM_ERRORS},
    dependencies=[Depends(rate_limit("narrative"))],
)
async def comparison_narrative_endpoint(body: ComparisonNarrativeRequest, request: Request, provider: LLM) -> NarrativeResponse:
    out = await comparison_narrative(provider, request.app.state.session_factory, DEFAULT_WORKSPACE_ID, body.baseline_run_id, body.run_ids, body.locale)
    return NarrativeResponse(text=out.text, verification=out.verification, locale=out.locale, model=out.model, prompt=out.prompt)


@router.post(
    "/scenarios/parse",
    response_model=ParseResult,
    responses={404: {"description": "Dataset or scenario not found"}, **LLM_ERRORS},
    dependencies=[Depends(rate_limit("copilot"))],
)
async def parse_scenario(body: ParseRequest, request: Request, provider: LLM) -> ParseResult:
    """Free text -> proposed typed changes, each validated and grounded in the sentence. Nothing is
    saved: the user adds the changes in Scenario Studio. A plain question yields no change."""
    return await parse_scenario_text(provider, request.app.state.session_factory, DEFAULT_WORKSPACE_ID, body)
