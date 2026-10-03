"""Copilot persistence and actions (phase 11).

The LLM turn itself lives in `ai/copilot.py`; this service stores conversations and messages,
prepares a turn (history, aliases and references of earlier turns) and records its result.
Proposed actions are stored *pending* with an expiry and an idempotency key: nothing is created
or run until the user confirms, a confirmed action runs once (a second confirm returns the stored
result), and an expired or rejected action can never run.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy.orm import Session

from ..ai.context import Aliases, PageContext, RefStore
from ..ai.copilot import HistoryItem, TurnResult, TurnState
from ..ai.guards import check_user_message, redact_secrets
from ..ai.tools.registry import ProposedAction
from ..core.errors import AppError, Conflict, NotFound, ValidationFailed
from ..core.hashing import sha256_of
from ..db.base import utcnow
from ..db.models import DEFAULT_WORKSPACE_ID, Conversation, CopilotAction, Message
from ..domain.report import ReportSpec
from ..domain.run_config import RunConfig
from ..domain.scenario import parse_change
from ..repositories.actions import ActionRepository
from ..repositories.conversations import ConversationRepository
from .optimization import CreatedRun, OptimizationService
from .reports import ReportService
from .scenarios import ScenarioService

ACTION_TTL = timedelta(minutes=30)
HISTORY_TURNS = 10


class ActionExpired(Conflict):
    code = "ACTION_EXPIRED"
    default_message = "This proposal has expired. Ask the copilot again."


class ActionAlreadyDecided(Conflict):
    code = "ACTION_ALREADY_DECIDED"
    default_message = "This proposal was already rejected."


@dataclass
class PreparedTurn:
    state: TurnState
    history: list[HistoryItem]
    user_message_id: str


@dataclass
class ConfirmOutcome:
    action: CopilotAction
    created_run: CreatedRun | None = None  # to be queued by the caller (needs the executor)
    already_executed: bool = False


def _title(text: str) -> str:
    line = " ".join(text.split())
    return line[:77] + "…" if len(line) > 80 else line


class CopilotService:
    def __init__(self, session: Session, *, workspace_id: str = DEFAULT_WORKSPACE_ID) -> None:
        self.session = session
        self.workspace_id = workspace_id
        self.conversations = ConversationRepository(session)
        self.actions = ActionRepository(session)

    # ---- conversations ------------------------------------------------------------------

    def create(self, *, title: str | None, context: PageContext | None) -> Conversation:
        return self.conversations.add(
            Conversation(
                workspace_id=self.workspace_id,
                title=(title or "Nouvelle conversation")[:160],
                context=context.model_dump(mode="json") if context else None,
                aliases={},
                refs={},
            )
        )

    def get(self, conversation_id: str) -> Conversation:
        conversation = self.conversations.get(conversation_id, self.workspace_id)
        if conversation is None:
            raise NotFound(f"Conversation '{conversation_id}' does not exist.", details={"conversation_id": conversation_id})
        return conversation

    def list(self, *, page: int, page_size: int) -> tuple[list[Conversation], int]:
        return self.conversations.list(self.workspace_id, page=page, page_size=page_size)

    def delete(self, conversation_id: str) -> None:
        self.conversations.delete(self.get(conversation_id))

    def messages(self, conversation_id: str) -> list[Message]:
        return self.conversations.messages(self.get(conversation_id).id)

    def actions_of(self, conversation_id: str) -> list[CopilotAction]:
        actions = self.actions.for_conversation(self.get(conversation_id).id)
        for action in actions:
            self._expire_if_needed(action)
        return actions

    # ---- turns -----------------------------------------------------------------------------

    def prepare_turn(self, conversation_id: str, text: str, page: PageContext | None) -> PreparedTurn:
        conversation = self.get(conversation_id)
        try:
            cleaned = check_user_message(text)
        except ValueError as exc:
            raise ValidationFailed("The message is empty.") from exc
        page = page or PageContext.model_validate(conversation.context or {})
        previous = self.conversations.messages(conversation.id, limit=2 * HISTORY_TURNS)
        history = [HistoryItem(m.role, m.content) for m in previous if m.role in ("user", "assistant")]  # type: ignore[arg-type]
        user_texts = [m.content for m in previous if m.role == "user"] + [cleaned]
        message = self.conversations.add_message(
            Message(conversation_id=conversation.id, role="user", content=cleaned, context=page.model_dump(mode="json"))
        )
        if not previous and conversation.title == "Nouvelle conversation":
            conversation.title = _title(cleaned)
        conversation.context = page.model_dump(mode="json")
        conversation.updated_at = utcnow()
        state = TurnState(
            workspace_id=self.workspace_id,
            page=page,
            aliases=Aliases.from_json(conversation.aliases),
            refs=RefStore.from_json(conversation.refs),
            user_text=cleaned,
            user_texts=user_texts,
        )
        return PreparedTurn(state, history, message.id)

    def save_turn(self, conversation_id: str, state: TurnState, result: TurnResult) -> tuple[Message, list[CopilotAction]]:
        conversation = self.get(conversation_id)
        message = self.conversations.add_message(
            Message(
                conversation_id=conversation.id,
                role="assistant",
                content=result.raw,
                rendered=result.rendered,
                verification=result.verification.to_json(),
                tool_trace=result.tool_trace,
                context=state.page.model_dump(mode="json"),
                prompt_id=result.prompt_id,
                model=result.model,
            )
        )
        conversation.aliases = state.aliases.to_json()
        conversation.refs = state.refs.to_json()
        conversation.updated_at = utcnow()
        actions = [self._propose(conversation.id, message.id, proposal) for proposal in _unique(state.actions)]
        return message, actions

    def save_error(self, conversation_id: str, text: str) -> Message:
        conversation = self.get(conversation_id)
        conversation.updated_at = utcnow()
        return self.conversations.add_message(
            Message(conversation_id=conversation.id, role="error", content=redact_secrets(text)[:1000])
        )

    def _propose(self, conversation_id: str, message_id: str, proposal: ProposedAction) -> CopilotAction:
        key = sha256_of({"conversation": conversation_id, "message": message_id, "kind": proposal.kind, "payload": proposal.payload})
        existing = self.actions.by_idempotency_key(key)
        if existing is not None:
            return existing
        return self.actions.add(
            CopilotAction(
                conversation_id=conversation_id,
                message_id=message_id,
                kind=proposal.kind,
                payload=proposal.payload,
                summary=proposal.summary[:2000],
                status="pending",
                idempotency_key=key,
                expires_at=utcnow() + ACTION_TTL,
            )
        )

    # ---- actions -------------------------------------------------------------------------

    def get_action(self, action_id: str, *, for_update: bool = False) -> CopilotAction:
        action = (self.actions.get_for_update if for_update else self.actions.get)(action_id, self.workspace_id)
        if action is None:
            raise NotFound(f"Action '{action_id}' does not exist.", details={"action_id": action_id})
        return action

    def _expire_if_needed(self, action: CopilotAction) -> bool:
        if action.status == "pending" and action.expires_at <= utcnow():
            action.status = "expired"
            self.session.flush()
        return action.status == "expired"

    def reject(self, action_id: str) -> CopilotAction:
        action = self.get_action(action_id, for_update=True)
        if self._expire_if_needed(action):
            raise ActionExpired(details={"action_id": action.id})
        if action.status == "pending":
            action.status = "rejected"
            action.decided_at = utcnow()
        elif action.status != "rejected":
            raise Conflict(f"This proposal is already {action.status}.", code="ACTION_ALREADY_DECIDED", details={"status": action.status})
        return action

    def confirm(self, action_id: str, narrative: dict[str, Any] | None = None) -> ConfirmOutcome:
        """Runs the proposal once. A second confirm of an executed action returns the stored result."""
        action = self.get_action(action_id, for_update=True)
        if action.status == "executed":
            return ConfirmOutcome(action, already_executed=True)
        if self._expire_if_needed(action):
            raise ActionExpired(details={"action_id": action.id})
        if action.status != "pending":
            raise ActionAlreadyDecided(f"This proposal is {action.status}.", details={"status": action.status})
        created: CreatedRun | None = None
        try:
            result, created = self._execute(action, narrative)
        except AppError as exc:
            # Nothing else was written in this transaction: undo the partial work, record the failure.
            self.session.rollback()
            action = self.get_action(action_id, for_update=True)
            action.status = "failed"
            action.error = exc.message[:1000]
            action.decided_at = utcnow()
            return ConfirmOutcome(action)
        action.status = "executed"
        action.result = result
        action.decided_at = utcnow()
        return ConfirmOutcome(action, created_run=created)

    def _execute(self, action: CopilotAction, narrative: dict[str, Any] | None) -> tuple[dict[str, Any], CreatedRun | None]:
        payload = action.payload
        if action.kind == "create_scenario":
            changes = [parse_change({**c, "source": "ai_proposed"}) for c in payload["changes"]]
            scenario = ScenarioService(self.session, workspace_id=self.workspace_id).create(
                name=payload["name"],
                dataset_id=payload.get("dataset_id"),
                version_no=payload.get("version_no"),
                parent_id=payload.get("parent_id"),
                changes=changes,
            )
            return {"scenario_id": scenario.id}, None
        if action.kind == "run_optimization":
            created = OptimizationService(self.session, workspace_id=self.workspace_id).create_run(
                dataset_id=payload.get("dataset_id"),
                scenario_id=payload.get("scenario_id"),
                config=RunConfig.model_validate(payload.get("config") or {}),
                label=payload.get("label"),
            )
            return {"run_id": created.run.id, "cache_hit": created.cache_hit}, created
        if action.kind == "generate_report":
            spec = ReportSpec.model_validate(payload)
            report = ReportService(self.session, workspace_id=self.workspace_id).create(spec, narrative)
            return {"report_id": report.id}, None
        raise ValidationFailed(f"Unknown action kind '{action.kind}'.")


def _unique(proposals: list[ProposedAction]) -> list[ProposedAction]:
    """The model sometimes repeats the same proposal in one turn: keep one of each."""
    seen: set[str] = set()
    out: list[ProposedAction] = []
    for p in proposals:
        key = sha256_of({"kind": p.kind, "payload": p.payload})
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out
