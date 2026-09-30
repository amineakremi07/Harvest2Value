"""Session helpers: one transaction per unit of work, FastAPI dependency, and schema setup."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import Request
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from ..core.config import BACKEND_DIR
from .models import DEFAULT_WORKSPACE_ID, Workspace

ALEMBIC_INI = BACKEND_DIR / "alembic.ini"
MIGRATIONS_DIR = BACKEND_DIR / "migrations"


@contextmanager
def unit_of_work(factory: sessionmaker[Session]) -> Iterator[Session]:
    """Commit on success, roll back on any error."""
    session = factory()
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()


def get_session(request: Request) -> Iterator[Session]:
    """Request-scoped transaction for v2 routes."""
    with unit_of_work(request.app.state.session_factory) as session:
        yield session


def alembic_config(database_url: str) -> Config:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(Path(MIGRATIONS_DIR)))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def upgrade_database(engine: Engine, database_url: str) -> None:
    """Apply Alembic migrations on the given engine (idempotent)."""
    config = alembic_config(database_url)
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


def ensure_default_workspace(factory: sessionmaker[Session], currency: str = "TND") -> None:
    with unit_of_work(factory) as session:
        if session.get(Workspace, DEFAULT_WORKSPACE_ID) is None:
            session.add(Workspace(id=DEFAULT_WORKSPACE_ID, name="Default workspace", currency=currency))
