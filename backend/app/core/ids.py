"""Identifier generation."""

import uuid


def new_id() -> str:
    """Random UUID4 as a string (portable primary key for SQLite and PostgreSQL)."""
    return str(uuid.uuid4())
