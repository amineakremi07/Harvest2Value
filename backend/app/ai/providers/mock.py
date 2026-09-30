"""Scripted provider for tests and offline demos: replays replies in order, records every call."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from .base import ChatMessage, LLMReply, ResponseFormat, ToolSpec


class MockScriptExhausted(RuntimeError):
    """More calls were made than scripted replies were provided."""


@dataclass
class MockCall:
    messages: list[ChatMessage]
    tools: list[ToolSpec]
    response_format: ResponseFormat | None
    temperature: float
    max_tokens: int


class MockProvider:
    name = "mock"
    configured = True

    def __init__(self, script: Iterable[LLMReply | str | Exception] = (), model: str = "mock") -> None:
        self.model = model
        self._script = list(script)
        self.calls: list[MockCall] = []

    def push(self, *items: LLMReply | str | Exception) -> None:
        self._script.extend(items)

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: Sequence[ToolSpec] | None = None,
        response_format: ResponseFormat | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> LLMReply:
        self.calls.append(
            MockCall(list(messages), list(tools or []), response_format, temperature, max_tokens)
        )
        if not self._script:
            raise MockScriptExhausted(f"MockProvider received call #{len(self.calls)} with no scripted reply left.")
        item = self._script.pop(0)
        if isinstance(item, Exception):
            raise item
        if isinstance(item, str):
            return LLMReply(content=item, finish_reason="stop", model=self.model)
        return item
