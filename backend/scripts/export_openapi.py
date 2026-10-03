"""Write the OpenAPI document of the API to frontend/lib/api/openapi.json.

Run from backend/:  .venv/Scripts/python scripts/export_openapi.py
Then, from frontend/:  npm run gen:api  (regenerates lib/api/schema.gen.ts).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.main import app  # noqa: E402

OUT_PATH = BACKEND_DIR.parent / "frontend" / "lib" / "api" / "openapi.json"


def main() -> None:
    OUT_PATH.write_text(json.dumps(app.openapi(), indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
