"""Groq (OpenAI-compatible) — the default provider."""

from __future__ import annotations

import httpx

from .openai_compatible import OpenAICompatibleProvider


class GroqProvider(OpenAICompatibleProvider):
    DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
    # Validated for tool calling (docs/v2/phase11-tool-calling-probe.md); override with LLM_MODEL.
    DEFAULT_MODEL = "openai/gpt-oss-120b"

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str | None = None,
        base_url: str | None = None,
        timeout_s: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        super().__init__(
            name="groq",
            base_url=base_url or self.DEFAULT_BASE_URL,
            model=model or self.DEFAULT_MODEL,
            api_key=api_key,
            timeout_s=timeout_s,
            transport=transport,
        )
