"""Alembic migrations match the ORM models; generated JSON Schema matches the committed file."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from app.db.base import Base
from app.db.engine import make_engine
from app.db.session import alembic_config, upgrade_database
from scripts.export_json_schema import SCHEMA_PATH, render


def test_migrations_match_models_and_downgrade(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'm.db').as_posix()}"
    engine = make_engine(url)
    try:
        upgrade_database(engine, url)
        with engine.connect() as conn:
            assert compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), Base.metadata) == []
            assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
            assert conn.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"

        upgrade_database(engine, url)  # idempotent

        config = alembic_config(url)
        with engine.begin() as conn:
            config.attributes["connection"] = conn
            command.downgrade(config, "base")
        with engine.connect() as conn:
            assert inspect(conn).get_table_names() == ["alembic_version"]
    finally:
        engine.dispose()


def test_committed_json_schema_is_up_to_date() -> None:
    assert SCHEMA_PATH.read_text(encoding="utf-8") == render(), (
        "data/schema.v2.json is stale: run `python scripts/export_json_schema.py` from backend/"
    )
