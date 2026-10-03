"""Typed application settings, read from the environment and optional .env files."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import AliasChoices, BaseModel, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = BACKEND_DIR.parent

LLMProviderName = Literal["groq", "nvidia_nim", "mock"]


class RateLimits(BaseModel):
    """Requests allowed per client per minute, by endpoint family."""

    default_per_minute: int = Field(default=120, ge=1)
    runs_per_minute: int = Field(default=30, ge=1)
    copilot_per_minute: int = Field(default=20, ge=1)
    narrative_per_minute: int = Field(default=10, ge=1)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Later files win: backend/.env overrides the repository-level .env.
        env_file=(REPO_DIR / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
        populate_by_name=True,
    )

    app_env: Literal["development", "test", "production"] = "development"
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:3000"]
    )
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'harvest2value.db').as_posix()}"

    llm_provider: LLMProviderName = "groq"
    # GROQ_API_KEY is accepted so existing .env files keep working.
    llm_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("LLM_API_KEY", "GROQ_API_KEY")
    )
    llm_model: str | None = None
    llm_base_url: str | None = None
    llm_timeout_s: float = Field(default=30.0, gt=0, le=300)
    # LLM_PROVIDER=mock only: JSON file of scripted replies (E2E tests, offline demos).
    llm_mock_script: Path | None = None

    solver_time_limit_s: int = Field(default=30, ge=1, le=600)
    solver_max_concurrency: int = Field(default=2, ge=1, le=16)

    rate_limits: RateLimits = Field(default_factory=RateLimits)
    max_body_bytes: int = Field(default=2_000_000, ge=1_024)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: Any) -> Any:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("llm_api_key", "llm_model", "llm_base_url", mode="before")
    @classmethod
    def _blank_to_none(cls, value: Any) -> Any:
        # An empty `LLM_MODEL=` line means "use the default", not "empty model name".
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def llm_configured(self) -> bool:
        return self.llm_provider == "mock" or self.llm_api_key is not None


@lru_cache
def get_settings() -> Settings:
    return Settings()
