"""NVIDIA NIM hosted API (OpenAI-compatible) — optional provider."""

from __future__ import annotations

import httpx

from .openai_compatible import OpenAICompatibleProvider


class NimProvider(OpenAICompatibleProvider):
    DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
    DEFAULT_MODEL = "meta/llama-3.1-70b-instruct"

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
            name="nvidia_nim",
            base_url=base_url or self.DEFAULT_BASE_URL,
            model=model or self.DEFAULT_MODEL,
            api_key=api_key,
            timeout_s=timeout_s,
            transport=transport,
        )
