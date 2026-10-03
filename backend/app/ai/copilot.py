"""The copilot turn: tool loop -> answer -> numeric verification (one regeneration) -> rendering.

Provider-agnostic (Groq, NIM, mock). Tools run in a worker thread, each in its own database
transaction. The turn yields events for streaming (tool calls, tool results) and ends with the
final answer: raw text with `{{ref:...}}`, rendered text, verification report and the proposed
actions (pending, to be confirmed by the user).
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy.orm import Session, sessionmaker
from starlette.concurrency import run_in_threadpool

from ..core.errors import LLMUpstreamError
from ..db.session import unit_of_work
from .context import Aliases, PageContext, RefStore
from .guards import history_message, redact_secrets, user_asks_for_change
from .prompts import load
from .providers import ChatMessage, LLMProvider, LLMReply, ToolSpec
from .rendering import Locale, detect_locale, render
from .tools.registry import ProposedAction, ToolContext, ToolOutcome, run_tool, specs
from .verification import NumericVerifier, VerificationReport, numbers_in_text

MAX_TOOL_ROUNDS = 5
MAX_CALLS_PER_ROUND = 6
MAX_HISTORY = 10
RATE_LIMIT_BACKOFF_S = 2.0

_NUMBER_WORDS = {
    "un": 1, "une": 1, "one": 1, "deux": 2, "two": 2, "trois": 3, "three": 3, "quatre": 4, "four": 4,
    "cinq": 5, "five": 5, "six": 6, "sept": 7, "seven": 7, "huit": 8, "eight": 8, "dix": 10, "ten": 10,
    "double": 2, "moitié": 50, "half": 50,
}


def user_numbers(texts: list[str]) -> list[float]:
    """Numbers the user typed in this conversation, in digits or (small ones) in words."""
    out: list[float] = []
    for text in texts:
        out += numbers_in_text(text)
        out += [float(_NUMBER_WORDS[w]) for w in re.findall(r"[a-zà-ÿ]+", text.lower()) if w in _NUMBER_WORDS]
    return out


@dataclass
class TurnState:
    workspace_id: str
    page: PageContext
    aliases: Aliases
    refs: RefStore
    user_text: str
    user_texts: list[str]
    currency: str = "TND"
    actions: list[ProposedAction] = field(default_factory=list)

    def tool_context(self, session: Session) -> ToolContext:
        return ToolContext(
            session=session,
            workspace_id=self.workspace_id,
            page=self.page,
            aliases=self.aliases,
            refs=self.refs,
            user_text=self.user_text,
            user_numbers=user_numbers(self.user_texts),
            asks_for_change=user_asks_for_change(self.user_text),
            currency=self.currency,
            actions=self.actions,
        )


@dataclass
class HistoryItem:
    role: Literal["user", "assistant"]
    content: str


@dataclass
class TurnEvent:
    event: Literal["tool_call", "tool_result", "answer", "error"]
    data: dict[str, Any]


@dataclass
class TurnResult:
    raw: str
    rendered: str
    verification: VerificationReport
    locale: Locale
    tool_trace: list[dict[str, Any]]
    prompt_id: str
    model: str


async def complete_with_retry(provider: LLMProvider, messages: list[ChatMessage], **kwargs: Any) -> LLMReply:
    """One retry after a short backoff on a rate limit (Groq on-demand TPM limits, see docs)."""
    try:
        return await provider.complete(messages, **kwargs)
    except LLMUpstreamError as exc:
        if exc.details.get("http_status") != 429:
            raise
        await asyncio.sleep(RATE_LIMIT_BACKOFF_S)
        return await provider.complete(messages, **kwargs)


def _system_message(state: TurnState, prompt_text: str) -> ChatMessage:
    page = {k: v for k, v in state.page.model_dump().items() if v}
    context = f"\n\n## Page context\n{json.dumps(page)}\nCall get_context to get aliases for these entities." if page else ""
    return ChatMessage(role="system", content=prompt_text + context)


async def verify_and_render(
    provider: LLMProvider,
    messages: list[ChatMessage],
    text: str,
    refs: RefStore,
    *,
    extra_numbers: list[float],
    locale: Locale,
    currency: str,
    max_tokens: int = 900,
) -> tuple[str, str, VerificationReport]:
    """Shared by the copilot and the narratives: verify, regenerate at most once, render, mark."""
    verifier = NumericVerifier(refs, user_numbers=extra_numbers)
    report = verifier.verify(text)
    if not report.ok:
        retry_messages = [*messages, ChatMessage(role="assistant", content=text), ChatMessage(role="user", content=report.feedback())]
        reply = await complete_with_retry(provider, retry_messages, max_tokens=max_tokens, temperature=0.1)
        if reply.content and reply.content.strip():
            text = reply.content.strip()
        report = verifier.verify(text)
        report.regenerated = True
    rendered = render(text, refs, locale=locale, default_currency=currency)
    marked = redact_secrets(verifier.mark(rendered.text))
    return redact_secrets(text), marked, report


class Copilot:
    def __init__(self, provider: LLMProvider, session_factory: sessionmaker[Session], *, tools: list[ToolSpec] | None = None) -> None:
        self.provider = provider
        self.session_factory = session_factory
        self.tools = tools if tools is not None else specs()

    def _run_tool(self, state: TurnState, name: str, arguments: str) -> ToolOutcome:
        with unit_of_work(self.session_factory) as session:
            ctx = state.tool_context(session)
            outcome = run_tool(ctx, name, arguments)
            state.currency = ctx.currency
            return outcome

    async def run_turn(
        self,
        state: TurnState,
        history: list[HistoryItem],
        *,
        on_result: Callable[[TurnResult], None] | None = None,
    ) -> AsyncIterator[TurnEvent]:
        prompt = load("copilot_system")
        locale = detect_locale(state.user_text)
        messages: list[ChatMessage] = [_system_message(state, prompt.text)]
        for item in history[-MAX_HISTORY:]:
            messages.append(ChatMessage(role=item.role, content=history_message(item.content)))
        messages.append(ChatMessage(role="user", content=state.user_text))

        trace: list[dict[str, Any]] = []
        seen_numbers: list[float] = []  # numbers inside backend text (alert messages, labels)
        text: str | None = None
        model = self.provider.model
        for round_no in range(MAX_TOOL_ROUNDS + 1):
            last_round = round_no == MAX_TOOL_ROUNDS
            reply = await complete_with_retry(
                self.provider, messages, tools=None if last_round else self.tools, max_tokens=1200, temperature=0.2
            )
            model = reply.model
            if not reply.tool_calls:
                text = (reply.content or "").strip()
                break
            calls = reply.tool_calls[:MAX_CALLS_PER_ROUND]
            messages.append(ChatMessage(role="assistant", content=reply.content, tool_calls=calls))
            for call in calls:
                yield TurnEvent("tool_call", {"name": call.name[:64], "arguments": call.arguments[:500]})
                outcome = await run_in_threadpool(self._run_tool, state, call.name, call.arguments)
                trace.append({"name": outcome.name[:64], "ok": outcome.ok, "summary": outcome.summary, "suspicious": outcome.suspicious})
                if outcome.ok:
                    seen_numbers += numbers_in_text(outcome.content)
                yield TurnEvent("tool_result", {"name": outcome.name[:64], "ok": outcome.ok, "summary": outcome.summary})
                messages.append(ChatMessage(role="tool", tool_call_id=call.id, content=outcome.content))
        if not text:
            text = "Je n'ai pas pu formuler de réponse. Reformulez la question, s'il vous plaît." if locale == "fr" else "I could not produce an answer. Please rephrase."

        raw, rendered, report = await verify_and_render(
            self.provider,
            messages,
            text,
            state.refs,
            extra_numbers=[*user_numbers(state.user_texts), *seen_numbers],
            locale=locale,
            currency=state.currency,
        )
        result = TurnResult(raw, rendered, report, locale, trace, prompt.id, model)
        if on_result is not None:
            on_result(result)
        yield TurnEvent("answer", {"content": rendered, "verification": report.to_json()})
