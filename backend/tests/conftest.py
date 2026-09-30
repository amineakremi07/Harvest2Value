"""Shared fixtures. Run from backend/: python -m pytest tests"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

LLM_ENV_VARS = ("LLM_PROVIDER", "LLM_API_KEY", "GROQ_API_KEY", "LLM_MODEL", "LLM_BASE_URL", "LLM_TIMEOUT_S")


@pytest.fixture
def clean_llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hide real keys: the v1 client calls load_dotenv() at import, which fills os.environ."""
    for name in LLM_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def make_settings(clean_llm_env: None) -> Callable[..., Settings]:
    def _make(**overrides: Any) -> Settings:
        return Settings(_env_file=None, **overrides)  # type: ignore[call-arg]

    return _make


@pytest.fixture
def make_client(make_settings: Callable[..., Settings], tmp_path: Path) -> Iterator[Callable[..., TestClient]]:
    """A started app (lifespan run) on its own temporary SQLite database."""
    clients: list[TestClient] = []

    def _make(**overrides: Any) -> TestClient:
        overrides.setdefault("database_url", f"sqlite:///{(tmp_path / f'test_{len(clients)}.db').as_posix()}")
        client = TestClient(create_app(make_settings(**overrides)), raise_server_exceptions=False)
        client.__enter__()
        clients.append(client)
        return client

    yield _make
    for client in clients:
        client.__exit__(None, None, None)
