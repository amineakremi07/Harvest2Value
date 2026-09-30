"""Write data/schema.v2.json from the Pydantic DatasetPayload model (the source of truth).

Run from backend/:  .venv/Scripts/python scripts/export_json_schema.py
A test fails if the committed file differs from what this script generates.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.domain.dataset import SCHEMA_VERSION, DatasetPayload  # noqa: E402

SCHEMA_PATH = BACKEND_DIR.parent / "data" / "schema.v2.json"


def build_schema() -> dict[str, Any]:
    schema = DatasetPayload.model_json_schema(mode="validation")
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"https://harvest2value.local/schema/dataset-{SCHEMA_VERSION}.json",
        **schema,
        "title": f"Harvest2Value dataset (schema {SCHEMA_VERSION})",
    }


def render() -> str:
    return json.dumps(build_schema(), indent=2, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    SCHEMA_PATH.write_text(render(), encoding="utf-8")
    print(f"wrote {SCHEMA_PATH}")
