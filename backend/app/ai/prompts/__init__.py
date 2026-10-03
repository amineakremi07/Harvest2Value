"""Versioned prompts. A prompt file is `<name>.v<N>.md`; the highest version is used and its
identifier (`name@vN`) is stored with every generated message for traceability."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent
_FILE = re.compile(r"^(?P<name>[a-z_]+)\.v(?P<version>\d+)\.md$")


@dataclass(frozen=True)
class Prompt:
    name: str
    version: int
    text: str

    @property
    def id(self) -> str:
        return f"{self.name}@v{self.version}"

    def format(self, **values: str) -> str:
        """`{key}` substitution that leaves other braces (JSON examples, {{ref:...}}) untouched."""
        text = self.text
        for key, value in values.items():
            text = text.replace("{" + key + "}", value)
        return text


@lru_cache
def load(name: str) -> Prompt:
    versions = [
        (int(m.group("version")), path)
        for path in PROMPTS_DIR.glob(f"{name}.v*.md")
        if (m := _FILE.match(path.name)) and m.group("name") == name
    ]
    if not versions:
        raise FileNotFoundError(f"No prompt named {name!r}")
    version, path = max(versions)
    return Prompt(name, version, path.read_text(encoding="utf-8").strip())
