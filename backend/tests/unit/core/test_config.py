from collections.abc import Callable

import pytest

from app.core.config import Settings


def test_defaults(make_settings: Callable[..., Settings]) -> None:
    s = make_settings()
    assert s.llm_provider == "groq"
    assert s.llm_api_key is None and not s.llm_configured
    assert s.cors_origins == ["http://localhost:5173", "http://localhost:3000"]


def test_groq_api_key_is_accepted_as_fallback(monkeypatch: pytest.MonkeyPatch, clean_llm_env: None) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "gsk_fallback")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.llm_api_key is not None and s.llm_api_key.get_secret_value() == "gsk_fallback"
    assert s.llm_configured


def test_llm_api_key_wins_over_groq_api_key(monkeypatch: pytest.MonkeyPatch, clean_llm_env: None) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "gsk_fallback")
    monkeypatch.setenv("LLM_API_KEY", "primary")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.llm_api_key is not None and s.llm_api_key.get_secret_value() == "primary"


def test_blank_values_mean_default(monkeypatch: pytest.MonkeyPatch, clean_llm_env: None) -> None:
    monkeypatch.setenv("LLM_API_KEY", "  ")
    monkeypatch.setenv("LLM_MODEL", "")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.llm_api_key is None and s.llm_model is None


def test_cors_origins_from_comma_separated_env(monkeypatch: pytest.MonkeyPatch, clean_llm_env: None) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "https://a.example, https://b.example")
    assert Settings(_env_file=None).cors_origins == ["https://a.example", "https://b.example"]  # type: ignore[call-arg]


def test_nested_rate_limits_from_env(monkeypatch: pytest.MonkeyPatch, clean_llm_env: None) -> None:
    monkeypatch.setenv("RATE_LIMITS__RUNS_PER_MINUTE", "5")
    assert Settings(_env_file=None).rate_limits.runs_per_minute == 5  # type: ignore[call-arg]


def test_mock_provider_counts_as_configured(make_settings: Callable[..., Settings]) -> None:
    assert make_settings(llm_provider="mock").llm_configured


def test_secret_is_not_printed(make_settings: Callable[..., Settings]) -> None:
    s = make_settings(llm_api_key="gsk_secret")
    assert "gsk_secret" not in repr(s) and "gsk_secret" not in str(s.model_dump())
