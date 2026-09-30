"""Field-level diff between two JSON documents (dataset versions, later scenario previews).

Lists of objects carrying an `id` (or `buyer_id` for routes) are matched by that key, so
reordering is not reported as a change and paths stay readable: `buyers[b1].price_per_kg`.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

_KEY_FIELDS = ("id", "buyer_id")


class FieldDiff(BaseModel):
    path: str
    kind: Literal["added", "removed", "changed"]
    before: Any = None
    after: Any = None


def _key_field(items: list[Any]) -> str | None:
    for field in _KEY_FIELDS:
        if items and all(isinstance(i, dict) and field in i for i in items):
            return field
    return None


def payload_diff(before: Any, after: Any, path: str = "") -> list[FieldDiff]:
    if isinstance(before, dict) and isinstance(after, dict):
        diffs: list[FieldDiff] = []
        for key in sorted(set(before) | set(after)):
            sub = f"{path}.{key}" if path else key
            if key not in before:
                diffs.append(FieldDiff(path=sub, kind="added", after=after[key]))
            elif key not in after:
                diffs.append(FieldDiff(path=sub, kind="removed", before=before[key]))
            else:
                diffs.extend(payload_diff(before[key], after[key], sub))
        return diffs

    if isinstance(before, list) and isinstance(after, list):
        key = _key_field(before + after)
        if key is not None:
            old = {item[key]: item for item in before}
            new = {item[key]: item for item in after}
            diffs = []
            for item_id in list(old) + [i for i in new if i not in old]:
                sub = f"{path}[{item_id}]"
                if item_id not in new:
                    diffs.append(FieldDiff(path=sub, kind="removed", before=old[item_id]))
                elif item_id not in old:
                    diffs.append(FieldDiff(path=sub, kind="added", after=new[item_id]))
                else:
                    diffs.extend(payload_diff(old[item_id], new[item_id], sub))
            return diffs
        if before != after:
            return [FieldDiff(path=path, kind="changed", before=before, after=after)]
        return []

    if before != after:
        return [FieldDiff(path=path, kind="changed", before=before, after=after)]
    return []
