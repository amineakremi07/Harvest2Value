"""AI narratives of a run and of a comparison. The facts are gathered by the same read tools as
the copilot (one LLM call, no tool calling), then verified and rendered the same way."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session, sessionmaker
from starlette.concurrency import run_in_threadpool

from ..db.session import unit_of_work
from .context import Aliases, PageContext, RefStore
from .copilot import complete_with_retry, verify_and_render
from .prompts import load
from .providers import ChatMessage, LLMProvider
from .rendering import Locale
from .tools import analysis, runs, scenarios
from .tools.common import RunArg, resolve_run
from .tools.registry import ToolContext, ToolFailure
from .verification import numbers_in_text


class NarrativeOut(BaseModel):
    text: str
    raw: str
    verification: dict[str, Any]
    prompt: str
    model: str
    locale: Locale


@dataclass
class _Facts:
    facts: dict[str, Any]
    refs: RefStore
    currency: str


def _context(session: Session, workspace_id: str, refs: RefStore, aliases: Aliases) -> ToolContext:
    return ToolContext(
        session=session,
        workspace_id=workspace_id,
        page=PageContext(),
        aliases=aliases,
        refs=refs,
        user_text="",
        user_numbers=[],
        asks_for_change=False,
    )


def run_facts(factory: sessionmaker[Session], workspace_id: str, run_id: str) -> _Facts:
    refs, aliases = RefStore(), Aliases()
    with unit_of_work(factory) as session:
        ctx = _context(session, workspace_id, refs, aliases)
        arg = RunArg(run_id=run_id)
        facts: dict[str, Any] = {}
        facts.update(runs.get_run(ctx, arg).facts)
        buyers = analysis.get_buyer_analysis(ctx, arg).facts
        facts.update({k: v for k, v in buyers.items() if any(f in k for f in ("buyer_name", "sold_kg", "net_price_per_kg", "net_revenue", "market_rank"))})
        explanation_cards = {}
        for card_id in _buyer_ids(buyers):
            try:
                card = runs.explain_decision(ctx, runs.DecisionArgs(run_id=run_id, entity_id=card_id)).facts
            except ToolFailure:
                continue
            explanation_cards.update({k: v for k, v in card.items() if ".limiting_factor.message" in k or ".decision" in k.split(".")[-1]})
        facts.update(explanation_cards)
        bottlenecks = runs.get_bottlenecks(ctx, arg).facts
        facts.update({k: v for k, v in bottlenecks.items() if any(k.startswith(p) for p in _first_items(bottlenecks, 2))})
        insights = runs.get_insights(ctx, arg).facts
        facts.update({k: v for k, v in insights.items() if k.endswith(".message")})
        return _Facts(facts, refs, ctx.currency)


def _buyer_ids(buyer_facts: dict[str, Any]) -> list[str]:
    ids = []
    for key in buyer_facts:
        parts = key.split(".")
        if len(parts) > 3 and parts[1] == "buyer_analysis" and parts[2] == "buyers" and parts[3] not in ids:
            ids.append(parts[3])
    return ids


def _first_items(facts: dict[str, Any], n: int) -> list[str]:
    prefixes: list[str] = []
    for key in facts:
        prefix = ".".join(key.split(".")[:3])
        if prefix not in prefixes:
            prefixes.append(prefix)
    return prefixes[:n]


def comparison_facts(factory: sessionmaker[Session], workspace_id: str, baseline_run_id: str, run_ids: list[str]) -> _Facts:
    refs, aliases = RefStore(), Aliases()
    with unit_of_work(factory) as session:
        ctx = _context(session, workspace_id, refs, aliases)
        facts = scenarios.compare_runs(ctx, scenarios.CompareArgs(baseline_run_id=baseline_run_id, run_ids=run_ids)).facts
        for run_id in [baseline_run_id, *run_ids]:
            alias = aliases.alias("run", run_id)
            run = resolve_run(ctx, run_id)
            facts[f"{alias}.label"] = run.label or alias
        return _Facts(facts, refs, ctx.currency)


async def generate(provider: LLMProvider, prompt_name: str, gathered: _Facts, locale: Locale) -> NarrativeOut:
    prompt = load(prompt_name)
    language = "French" if locale == "fr" else "English"
    messages = [
        ChatMessage(role="system", content=prompt.format(language=language)),
        ChatMessage(role="user", content=json.dumps({"facts": gathered.facts}, ensure_ascii=False, default=str)),
    ]
    reply = await complete_with_retry(provider, messages, max_tokens=900, temperature=0.3)
    raw, rendered, report = await verify_and_render(
        provider,
        messages,
        (reply.content or "").strip(),
        gathered.refs,
        extra_numbers=numbers_in_text(json.dumps(gathered.facts, default=str)),
        locale=locale,
        currency=gathered.currency,
    )
    return NarrativeOut(text=rendered, raw=raw, verification=report.to_json(), prompt=prompt.id, model=reply.model, locale=locale)


async def run_narrative(provider: LLMProvider, factory: sessionmaker[Session], workspace_id: str, run_id: str, locale: Locale = "fr") -> NarrativeOut:
    gathered = await run_in_threadpool(run_facts, factory, workspace_id, run_id)
    return await generate(provider, "narrative_run", gathered, locale)


async def comparison_narrative(
    provider: LLMProvider, factory: sessionmaker[Session], workspace_id: str, baseline_run_id: str, run_ids: list[str], locale: Locale = "fr"
) -> NarrativeOut:
    gathered = await run_in_threadpool(comparison_facts, factory, workspace_id, baseline_run_id, run_ids)
    return await generate(provider, "narrative_comparison", gathered, locale)
