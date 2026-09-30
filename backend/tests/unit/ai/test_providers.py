"""R10: each provider hits the right URL with the right headers; errors are mapped; mock is scriptable."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from app.ai.providers import ChatMessage, LLMReply, ToolCall, ToolSpec, describe_llm, get_provider
from app.ai.providers.groq import GroqProvider
from app.ai.providers.mock import MockProvider, MockScriptExhausted
from app.ai.providers.nim import NimProvider
from app.core.config import Settings
from app.core.errors import LLMNotConfigured, LLMTimeout, LLMUpstreamError

USER = [ChatMessage(role="user", content="hi")]


def ok_body(content: str | None = "hello", tool_calls: list[dict[str, Any]] | None = None, finish: str = "stop") -> dict[str, Any]:
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls is not None:
        message["tool_calls"] = tool_calls
    return {
        "model": "served-model",
        "choices": [{"message": message, "finish_reason": finish}],
        "usage": {"prompt_tokens": 7, "completion_tokens": 3},
    }


class Recorder:
    """httpx.MockTransport handler that records requests and returns a canned response."""

    def __init__(self, status: int = 200, body: dict[str, Any] | None = None, exc: Exception | None = None) -> None:
        self.status, self.body, self.exc = status, body if body is not None else ok_body(), exc
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.exc is not None:
            raise self.exc
        return httpx.Response(self.status, json=self.body)

    @property
    def payload(self) -> dict[str, Any]:
        return json.loads(self.requests[-1].content)


def run(coro: Any) -> Any:
    return asyncio.run(coro)


# ---- R10: URL, headers, model per provider ----

@pytest.mark.parametrize(
    ("provider_cls", "url", "model"),
    [
        (GroqProvider, "https://api.groq.com/openai/v1/chat/completions", "openai/gpt-oss-120b"),
        (NimProvider, "https://integrate.api.nvidia.com/v1/chat/completions", "meta/llama-3.1-70b-instruct"),
    ],
)
def test_provider_url_headers_and_default_model(provider_cls: Callable[..., Any], url: str, model: str) -> None:
    rec = Recorder()
    provider = provider_cls(api_key="secret-key", transport=httpx.MockTransport(rec))

    reply = run(provider.complete(USER))

    request = rec.requests[0]
    assert str(request.url) == url
    assert request.method == "POST"
    assert request.headers["authorization"] == "Bearer secret-key"
    assert request.headers["content-type"] == "application/json"
    assert rec.payload["model"] == model
    assert rec.payload["messages"] == [{"role": "user", "content": "hi"}]
    assert reply.content == "hello" and reply.model == "served-model"
    assert reply.usage is not None and reply.usage.prompt_tokens == 7


def test_base_url_and_model_overrides() -> None:
    rec = Recorder()
    provider = GroqProvider(
        api_key="k", model="custom-model", base_url="https://proxy.example/v1/", transport=httpx.MockTransport(rec)
    )
    run(provider.complete(USER))
    assert str(rec.requests[0].url) == "https://proxy.example/v1/chat/completions"
    assert rec.payload["model"] == "custom-model"


def test_factory_builds_provider_from_settings(make_settings: Callable[..., Settings]) -> None:
    nim = get_provider(make_settings(llm_provider="nvidia_nim", llm_api_key="k", llm_model="m"))
    assert isinstance(nim, NimProvider) and nim.model == "m"
    assert isinstance(get_provider(make_settings()), GroqProvider)
    assert isinstance(get_provider(make_settings(llm_provider="mock")), MockProvider)


def test_describe_llm_never_contains_the_key(make_settings: Callable[..., Settings]) -> None:
    info = describe_llm(make_settings(llm_api_key="gsk_do_not_leak"))
    assert info == {"provider": "groq", "model": "openai/gpt-oss-120b", "configured": True}
    assert "gsk_do_not_leak" not in json.dumps(info)


# ---- payload shape ----

def test_tools_and_json_mode_payload() -> None:
    rec = Recorder()
    provider = GroqProvider(api_key="k", transport=httpx.MockTransport(rec))
    tool = ToolSpec(name="get_run", description="Read a run", parameters={"type": "object", "properties": {}})

    run(provider.complete(USER, tools=[tool], response_format="json_object", temperature=0.1, max_tokens=50))

    p = rec.payload
    assert p["tools"] == [{"type": "function", "function": {"name": "get_run", "description": "Read a run", "parameters": {"type": "object", "properties": {}}}}]
    assert p["tool_choice"] == "auto"
    assert p["response_format"] == {"type": "json_object"}
    assert (p["temperature"], p["max_tokens"]) == (0.1, 50)


def test_no_tools_means_no_tool_keys() -> None:
    rec = Recorder()
    run(GroqProvider(api_key="k", transport=httpx.MockTransport(rec)).complete(USER))
    assert "tools" not in rec.payload and "tool_choice" not in rec.payload and "response_format" not in rec.payload


def test_tool_call_round_trip() -> None:
    rec = Recorder(body=ok_body(content=None, tool_calls=[
        {"id": "call_1", "type": "function", "function": {"name": "get_run", "arguments": '{"run_id": "r1"}'}}
    ], finish="tool_calls"))
    provider = GroqProvider(api_key="k", transport=httpx.MockTransport(rec))

    reply = run(provider.complete(USER))
    assert reply.content is None
    assert reply.tool_calls == [ToolCall(id="call_1", name="get_run", arguments='{"run_id": "r1"}')]

    # The assistant turn and the tool result are sent back in OpenAI wire format.
    history = [
        *USER,
        ChatMessage(role="assistant", tool_calls=reply.tool_calls),
        ChatMessage(role="tool", tool_call_id="call_1", content='{"status": "succeeded"}'),
    ]
    rec.body = ok_body("done")
    run(provider.complete(history))
    sent = rec.payload["messages"]
    assert sent[1] == {"role": "assistant", "content": None, "tool_calls": [
        {"id": "call_1", "type": "function", "function": {"name": "get_run", "arguments": '{"run_id": "r1"}'}}
    ]}
    assert sent[2] == {"role": "tool", "content": '{"status": "succeeded"}', "tool_call_id": "call_1"}


# ---- error mapping ----

def test_missing_key_raises_not_configured_without_calling_out() -> None:
    rec = Recorder()
    with pytest.raises(LLMNotConfigured):
        run(GroqProvider(api_key=None, transport=httpx.MockTransport(rec)).complete(USER))
    assert rec.requests == []


def test_http_error_is_upstream_error_without_key() -> None:
    rec = Recorder(status=401, body={"error": {"message": "Invalid API Key"}})
    with pytest.raises(LLMUpstreamError) as exc:
        run(GroqProvider(api_key="secret-key", transport=httpx.MockTransport(rec)).complete(USER))
    assert "HTTP 401" in exc.value.message and "Invalid API Key" in exc.value.message
    assert exc.value.details["http_status"] == 401
    assert "secret-key" not in exc.value.message + json.dumps(exc.value.details)


def test_timeout_maps_to_llm_timeout() -> None:
    rec = Recorder(exc=httpx.ReadTimeout("slow"))
    with pytest.raises(LLMTimeout):
        run(GroqProvider(api_key="k", transport=httpx.MockTransport(rec)).complete(USER))


def test_network_error_maps_to_upstream_error() -> None:
    rec = Recorder(exc=httpx.ConnectError("down"))
    with pytest.raises(LLMUpstreamError, match="Could not reach"):
        run(GroqProvider(api_key="k", transport=httpx.MockTransport(rec)).complete(USER))


@pytest.mark.parametrize(
    ("body", "match"),
    [
        (ok_body(finish="length"), "cut off"),
        (ok_body(content="   "), "empty"),
        ({"choices": []}, "choices"),
        (ok_body(content=None, tool_calls=[{"id": "x", "type": "function"}]), "malformed tool call"),
    ],
)
def test_unusable_replies(body: dict[str, Any], match: str) -> None:
    rec = Recorder(body=body)
    with pytest.raises(LLMUpstreamError, match=match):
        run(GroqProvider(api_key="k", transport=httpx.MockTransport(rec)).complete(USER))


# ---- mock provider ----

def test_mock_replays_script_and_records_calls() -> None:
    mock = MockProvider(["first", LLMReply(content=None, tool_calls=[ToolCall(id="t", name="get_run", arguments="{}")], model="mock")])
    tool = ToolSpec(name="get_run", description="d", parameters={"type": "object"})

    assert run(mock.complete(USER)).content == "first"
    second = run(mock.complete(USER, tools=[tool], response_format="json_object"))

    assert second.tool_calls[0].name == "get_run"
    assert len(mock.calls) == 2
    assert mock.calls[1].tools == [tool] and mock.calls[1].response_format == "json_object"


def test_mock_raises_scripted_exceptions_then_reports_exhaustion() -> None:
    mock = MockProvider([LLMTimeout()])
    with pytest.raises(LLMTimeout):
        run(mock.complete(USER))
    with pytest.raises(MockScriptExhausted):
        run(mock.complete(USER))
    mock.push("again")
    assert run(mock.complete(USER)).content == "again"
