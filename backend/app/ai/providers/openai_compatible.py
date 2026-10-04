"""Shared client for OpenAI-compatible /chat/completions endpoints.

Error handling: timeouts, transport errors, HTTP errors, missing choices, truncated (`finish_reason="length"`)
and empty replies. The API key never appears in errors or logs.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

import httpx

from ...core.errors import LLMNotConfigured, LLMTimeout, LLMUpstreamError
from .base import ChatMessage, LLMReply, LLMUsage, ResponseFormat, ToolCall, ToolSpec

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider:
    def __init__(
        self,
        *,
        name: str,
        base_url: str,
        model: str,
        api_key: str | None,
        timeout_s: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.name = name
        self.model = model
        self.endpoint = base_url.rstrip("/") + "/chat/completions"
        self._api_key = api_key
        self._timeout_s = timeout_s
        self._transport = transport  # injected in tests (httpx.MockTransport)

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    def _headers(self) -> dict[str, str]:
        if not self._api_key:
            raise LLMNotConfigured(
                f"No API key is configured for the '{self.name}' provider (set LLM_API_KEY).",
                details={"provider": self.name},
            )
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def build_payload(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: Sequence[ToolSpec] | None,
        response_format: ResponseFormat | None,
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [_message_to_wire(m) for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {"name": t.name, "description": t.description, "parameters": t.parameters},
                }
                for t in tools
            ]
            payload["tool_choice"] = "auto"
        if response_format == "json_object":
            payload["response_format"] = {"type": "json_object"}
        return payload

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: Sequence[ToolSpec] | None = None,
        response_format: ResponseFormat | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> LLMReply:
        headers = self._headers()
        payload = self.build_payload(
            messages,
            tools=tools,
            response_format=response_format,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        details = {"provider": self.name, "model": self.model}

        try:
            async with httpx.AsyncClient(timeout=self._timeout_s, transport=self._transport) as client:
                response = await client.post(self.endpoint, json=payload, headers=headers)
        except httpx.TimeoutException as e:
            raise LLMTimeout(
                f"The '{self.name}' AI service did not answer within {self._timeout_s:.0f}s.",
                details=details,
            ) from e
        except httpx.RequestError as e:
            raise LLMUpstreamError(
                f"Could not reach the '{self.name}' AI service ({type(e).__name__}).",
                details=details,
            ) from e

        if response.is_error:
            logger.warning(
                "LLM HTTP error",
                extra={"provider": self.name, "model": self.model, "http_status": response.status_code},
            )
            raise LLMUpstreamError(
                f"The '{self.name}' AI service returned HTTP {response.status_code}: "
                f"{_error_message(response)}",
                details={**details, "http_status": response.status_code},
            )

        return _parse_reply(response, self.model, details)


def _message_to_wire(message: ChatMessage) -> dict[str, Any]:
    wire: dict[str, Any] = {"role": message.role, "content": message.content}
    if message.tool_calls:
        wire["tool_calls"] = [
            {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.arguments}}
            for c in message.tool_calls
        ]
    if message.tool_call_id is not None:
        wire["tool_call_id"] = message.tool_call_id
    return wire


def _error_message(response: httpx.Response) -> str:
    try:
        return str(response.json()["error"]["message"])[:300]
    except (ValueError, KeyError, TypeError):
        return response.text[:300] or response.reason_phrase


def _parse_reply(response: httpx.Response, fallback_model: str, details: dict[str, Any]) -> LLMReply:
    try:
        body = response.json()
        choice = body["choices"][0]
        message = choice["message"]
    except (ValueError, KeyError, IndexError, TypeError) as e:
        raise LLMUpstreamError("The AI service response did not contain choices[0].message.", details=details) from e

    # Reasoning models spend completion tokens before answering: a truncated reply
    # would yield broken JSON or a cut-off answer.
    if choice.get("finish_reason") == "length":
        raise LLMUpstreamError(
            "The AI service reply was cut off (finish_reason='length'); increase max_tokens.",
            details=details,
        )

    try:
        tool_calls = [
            ToolCall(id=c["id"], name=c["function"]["name"], arguments=c["function"].get("arguments") or "{}")
            for c in (message.get("tool_calls") or [])
        ]
    except (KeyError, TypeError) as e:
        raise LLMUpstreamError("The AI service returned a malformed tool call.", details=details) from e

    content = message.get("content")
    if not tool_calls and (not isinstance(content, str) or not content.strip()):
        raise LLMUpstreamError("The AI service returned an empty response.", details=details)

    usage_raw = body.get("usage") or {}
    return LLMReply(
        content=content if isinstance(content, str) else None,
        tool_calls=tool_calls,
        finish_reason=choice.get("finish_reason"),
        model=str(body.get("model") or fallback_model),
        usage=LLMUsage(
            prompt_tokens=int(usage_raw.get("prompt_tokens") or 0),
            completion_tokens=int(usage_raw.get("completion_tokens") or 0),
        ),
    )
