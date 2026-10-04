"""Free text -> proposed scenario changes (never saved here: the user adds them in Scenario Studio).

Guarantees, whatever the model answers:
- R6: a question without a request to change ("quel est le profit pour 12 000 kg ?") yields no
  change, and the model is not even called;
- every change is validated (typed op, existing target, applies on the effective data);
- every numeric parameter appears in the user's sentence (no invented values);
- the sentence is data for the model, never instructions (guards + prompt).
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session, sessionmaker
from starlette.concurrency import run_in_threadpool

from ..ai.copilot import complete_with_retry, user_numbers
from ..ai.guards import check_user_message, numeric_params, ungrounded_numbers, user_asks_for_change
from ..ai.prompts import load
from ..ai.providers import ChatMessage, LLMProvider
from ..ai.tools.data import _compact_schema
from ..core.errors import LLMUpstreamError, ScenarioApplyError
from ..db.session import unit_of_work
from ..domain.dataset import DatasetPayload
from ..domain.scenario import CHANGE_TYPES, parse_change
from ..services.scenarios import ScenarioService
from .apply import ChangeRef, apply_changes


class ParseRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    dataset_id: str | None = Field(default=None, max_length=64)
    scenario_id: str | None = Field(default=None, max_length=64, description="Parse against this scenario's effective data")


class ProposedChange(BaseModel):
    op: str
    target: str | None
    params: dict[str, Any]
    summary: str = Field(description="What the change does, computed by the backend")
    quote: str | None = None


class RejectedChange(BaseModel):
    change: dict[str, Any]
    reason: str


class ParseResult(BaseModel):
    changes: list[ProposedChange]
    rejected: list[RejectedChange]
    questions: list[str]
    prompt: str | None = None
    model: str | None = None


_QUESTION = re.compile(r"^\s*(quel|quelle|quels|quelles|combien|est-ce|pourquoi|comment|o[uù]|qui|what|which|how|why|is|are|does|do)\b", re.I)


def is_plain_question(text: str) -> bool:
    return not user_asks_for_change(text) and (text.strip().endswith("?") or bool(_QUESTION.match(text)))


def _effective_payload(session: Session, workspace_id: str, request: ParseRequest) -> tuple[DatasetPayload, list[ChangeRef]]:
    service = ScenarioService(session, workspace_id=workspace_id)
    if request.scenario_id:
        scenario = service.get(request.scenario_id)
        version = service.base_version(scenario)
        return DatasetPayload.model_validate(version.payload), service.chain_changes(scenario)
    if not request.dataset_id:
        raise ScenarioApplyError("Provide dataset_id or scenario_id.", code="VALIDATION_ERROR")
    preview = service.apply_preview(request.dataset_id, None, [])
    return preview.effective, []


def _entities(payload: DatasetPayload) -> str:
    lines = ["buyers: " + ", ".join(f"{b.id} ({b.name})" for b in payload.buyers)]
    lines.append("harvest lots: " + ", ".join(f"{l.id} ({l.quantity_kg:g} kg, day {l.available_day})" for l in payload.harvest_lots))
    lines.append("storage: " + (", ".join(f"{f.id} ({f.name})" for f in payload.storage_facilities) or "none"))
    lines.append("vehicles: " + ", ".join(f"{v.id} ({v.name})" for v in payload.vehicle_types))
    lines.append("crops: " + ", ".join(f"{c.id} ({c.name})" for c in payload.crops))
    return "\n".join(lines)


def _operations() -> str:
    return "\n".join(
        f"- {op}: target {t.target_kind}, params {_compact_schema(t.model_fields['params'].annotation.model_json_schema())}"  # type: ignore[union-attr]
        for op, t in CHANGE_TYPES.items()
    )


def _parse_json(content: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", content, re.S)
    if not match:
        raise LLMUpstreamError("The AI service did not return JSON.")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise LLMUpstreamError("The AI service returned malformed JSON.") from exc
    return data if isinstance(data, dict) else {}


def validate_proposals(payload: DatasetPayload, chain: list[ChangeRef], text: str, raw_changes: list[Any]) -> tuple[list[ProposedChange], list[RejectedChange]]:
    accepted: list[ProposedChange] = []
    rejected: list[RejectedChange] = []
    allowed = user_numbers([text])
    refs = list(chain)
    for item in raw_changes[:10]:
        if not isinstance(item, dict):
            continue
        change_dict = {k: item.get(k) for k in ("op", "target", "params")}
        change_dict["params"] = change_dict["params"] if isinstance(change_dict["params"], dict) else {}
        try:
            change = parse_change({**change_dict, "source": "ai_proposed"})
        except ValidationError as exc:
            rejected.append(RejectedChange(change=change_dict, reason="; ".join(e["msg"] for e in exc.errors(include_url=False))[:300]))
            continue
        missing = ungrounded_numbers(numeric_params(change_dict["params"]), allowed)
        if missing:
            rejected.append(RejectedChange(change=change_dict, reason=f"valeur(s) absente(s) de la phrase : {', '.join(f'{m:g}' for m in missing)}"))
            continue
        try:
            applied = apply_changes(payload, [*refs, ChangeRef(change, None, None)])
        except ScenarioApplyError as exc:
            rejected.append(RejectedChange(change=change_dict, reason=exc.message[:300]))
            continue
        refs.append(ChangeRef(change, None, None))
        dumped = change.model_dump(mode="json")
        quote = item.get("quote")
        accepted.append(
            ProposedChange(op=dumped["op"], target=dumped["target"], params=dumped["params"], summary=applied.applied[-1].summary, quote=quote if isinstance(quote, str) else None)
        )
    return accepted, rejected


async def parse_scenario_text(provider: LLMProvider, factory: sessionmaker[Session], workspace_id: str, request: ParseRequest) -> ParseResult:
    text = check_user_message(request.text)
    if is_plain_question(text):
        return ParseResult(
            changes=[],
            rejected=[],
            questions=["Cette phrase est une question, pas une modification. Formulez un « et si » (ex. « et si le prix baisse de 10 % »)."],
        )

    def load_payload() -> tuple[DatasetPayload, list[ChangeRef]]:
        with unit_of_work(factory) as session:
            return _effective_payload(session, workspace_id, request)

    payload, chain = await run_in_threadpool(load_payload)
    effective = apply_changes(payload, chain).effective if chain else payload
    prompt = load("parse_changes")
    messages = [
        ChatMessage(role="system", content=prompt.format(operations=_operations(), entities=_entities(effective))),
        ChatMessage(role="user", content=json.dumps({"sentence": text}, ensure_ascii=False)),
    ]
    reply = await complete_with_retry(provider, messages, response_format="json_object", max_tokens=900, temperature=0.0)
    data = _parse_json(reply.content or "")
    changes_value = data.get("changes")
    raw_changes: list[Any] = changes_value if isinstance(changes_value, list) else []
    questions = [str(q)[:300] for q in data.get("questions", []) if isinstance(q, (str, int, float))][:5] if isinstance(data.get("questions"), list) else []
    accepted, rejected = validate_proposals(payload, chain, text, raw_changes)
    return ParseResult(changes=accepted, rejected=rejected, questions=questions, prompt=prompt.id, model=reply.model)
