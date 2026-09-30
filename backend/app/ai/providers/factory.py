"""Build the configured provider and describe it without exposing the key."""

from __future__ import annotations

from typing import Any

from ...core.config import Settings
from .base import LLMProvider
from .groq import GroqProvider
from .mock import MockProvider
from .nim import NimProvider


def get_provider(settings: Settings) -> LLMProvider:
    """A provider is always returned; a missing key surfaces as LLMNotConfigured on first call."""
    if settings.llm_provider == "mock":
        return MockProvider()

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
