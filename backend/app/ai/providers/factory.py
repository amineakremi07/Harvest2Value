"""Build the configured provider and describe it without exposing the key."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...core.config import Settings
from .base import LLMProvider, LLMReply, ToolCall
from .groq import GroqProvider
from .mock import MockProvider
from .nim import NimProvider


def get_provider(settings: Settings) -> LLMProvider:
    """A provider is always returned; a missing key surfaces as LLMNotConfigured on first call."""
    if settings.llm_provider == "mock":
        return MockProvider(load_script(settings.llm_mock_script) if settings.llm_mock_script else ())

    api_key = settings.llm_api_key.get_secret_value() if settings.llm_api_key else None
    provider_cls = GroqProvider if settings.llm_provider == "groq" else NimProvider
    return provider_cls(
        api_key=api_key,
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        timeout_s=settings.llm_timeout_s,
    )


def describe_llm(settings: Settings) -> dict[str, Any]:
    provider = get_provider(settings)
    return {
        "provider": settings.llm_provider,
        "model": provider.model,
        "configured": settings.llm_configured,
    }


def load_script(path: Path) -> list[LLMReply | str]:
    """Mock script: a JSON list whose items are either the answer text, or
    `{"tool_calls": [{"name": ..., "arguments": {...}}]}`."""
    items: list[LLMReply | str] = []
    for i, item in enumerate(json.loads(path.read_text(encoding="utf-8"))):
        if isinstance(item, str):
            items.append(item)
            continue
        calls = [
            ToolCall(id=f"mock-{i}-{j}", name=c["name"], arguments=json.dumps(c.get("arguments", {})))
            for j, c in enumerate(item["tool_calls"])
        ]
        items.append(LLMReply(tool_calls=calls, finish_reason="tool_calls", model="mock"))
    return items
