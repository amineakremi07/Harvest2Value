"""Copilot context: what the user is looking at, short aliases for entities, and the reference
store that backs every number the assistant may state.

Numbers never travel from the LLM to the user. Tools return values together with reference keys
(`r1.kpis.realized_profit`); the model writes `{{ref:r1.kpis.realized_profit}}` and the backend
renders the value (rendering.py). Aliases (`r1`, `d1`, `s1`, `c1`) keep keys short and stable
within a conversation, so the model never copies UUIDs or invents paths.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field

Unit = Literal["currency", "currency/kg", "kg", "%", "days", "trips", "hours", "km", "count", "number"]
EntityKind = Literal["run", "dataset", "scenario", "comparison", "report"]

ALIAS_PREFIX: dict[EntityKind, str] = {"run": "r", "dataset": "d", "scenario": "s", "comparison": "c", "report": "p"}
REF_KEY = re.compile(r"^[A-Za-z0-9_.\-]{1,200}$")


class PageContext(BaseModel):
    """What the user has open when asking (sent by the frontend, validated, never trusted blindly)."""

    page: str | None = Field(default=None, max_length=200)
    run_id: str | None = Field(default=None, max_length=64)
    dataset_id: str | None = Field(default=None, max_length=64)
    scenario_id: str | None = Field(default=None, max_length=64)
    compare_run_ids: list[str] = Field(default_factory=list, max_length=4)


@dataclass(frozen=True)
class RefValue:
    value: float
    unit: Unit
    currency: str | None = None


_GENERIC = ("delta", "before", "after", "value", "limit", "abs")


def unit_for(key: str) -> Unit:
    """Unit of a numeric field, from its name (backend naming conventions). Generic leaf names
    (`delta`, `before`, `after`...) take the unit of their parent field."""
    parts = key.split(".")
    name = parts[-1]
    if name == "delta_pct":
        return "%"
    if name in _GENERIC and len(parts) > 1:
        parent = unit_for(".".join(parts[:-1]))
        if parent != "number":
            return parent
    if name.endswith("_pct") or name in ("margin", "share"):
        return "%"
    if name.endswith(("per_kg", "_price")) or name == "price" or name == "unit_price":
        return "currency/kg"
    if name.endswith("_kg") or name in ("kg", "quantity"):
        return "kg"
    if name.endswith("_days") or name in ("day", "horizon"):
        return "days"
    if name in ("trips",) or name.endswith("_trips"):
        return "trips"
    if name.endswith("_hours") or name == "hours":
        return "hours"
    if name.endswith("_km"):
        return "km"
    if name.endswith("_count") or name in ("count", "rank", "market_rank", "lot_count", "buyer_count", "version_no"):
        return "count"
    if any(word in name for word in ("profit", "revenue", "cost", "value", "objective", "toll", "delta", "gain", "dual")):
        return "currency"
    return "number"


@dataclass
class RefStore:
    """Every number a tool returned in this turn (or earlier turns), by reference key."""

    values: dict[str, RefValue] = field(default_factory=dict)

    def add(self, key: str, value: float, unit: Unit | None = None, currency: str | None = None) -> str:
        if not REF_KEY.match(key) or not math.isfinite(value):
            raise ValueError(f"invalid reference {key!r}")
        self.values[key] = RefValue(float(value), unit or unit_for(key), currency)
        return key

    def get(self, key: str) -> RefValue | None:
        return self.values.get(key)

    def __contains__(self, key: object) -> bool:
        return key in self.values

    def numbers(self) -> list[float]:
        return [v.value for v in self.values.values()]

    def to_json(self) -> dict[str, Any]:
        return {k: {"value": v.value, "unit": v.unit, "currency": v.currency} for k, v in self.values.items()}

    @classmethod
    def from_json(cls, data: Mapping[str, Any] | None) -> RefStore:
        store = cls()
        for key, item in (data or {}).items():
            try:
                store.add(key, float(item["value"]), item.get("unit"), item.get("currency"))
            except (KeyError, TypeError, ValueError):
                continue
        return store


@dataclass
class Aliases:
    """Short, stable names (`r1`, `d2`) for the entities a conversation touches."""

    by_alias: dict[str, tuple[EntityKind, str]] = field(default_factory=dict)

    def alias(self, kind: EntityKind, entity_id: str) -> str:
        for alias, (k, eid) in self.by_alias.items():
            if k == kind and eid == entity_id:
                return alias
        prefix = ALIAS_PREFIX[kind]
        n = 1 + sum(1 for a in self.by_alias if a.startswith(prefix) and a[len(prefix) :].isdigit())
        alias = f"{prefix}{n}"
        self.by_alias[alias] = (kind, entity_id)
        return alias

    def resolve(self, kind: EntityKind, value: str | None) -> str | None:
        """An alias (`r2`) or a raw id -> the entity id (raw ids pass through unchanged)."""
        if value is None:
            return None
        found = self.by_alias.get(value.strip())
        if found is not None:
            return found[1] if found[0] == kind else None
        return value.strip()

    def to_json(self) -> dict[str, list[str]]:
        return {a: [k, eid] for a, (k, eid) in self.by_alias.items()}

    @classmethod
    def from_json(cls, data: Mapping[str, Any] | None) -> Aliases:
        aliases = cls()
        for alias, pair in (data or {}).items():
            if isinstance(pair, (list, tuple)) and len(pair) == 2 and pair[0] in ALIAS_PREFIX:
                aliases.by_alias[alias] = (pair[0], str(pair[1]))
        return aliases


_ID_FIELDS = ("buyer_id", "id", "lot_id", "facility_id", "vehicle_type_id", "kpi", "key", "day")


def _segment(item: Mapping[str, Any], index: int) -> str:
    for name in _ID_FIELDS:
        value = item.get(name)
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            text = re.sub(r"[^A-Za-z0-9_\-]", "_", str(value))[:64]
            return f"d{text}" if name == "day" else text
    return str(index)


def register_numbers(store: RefStore, prefix: str, data: Any, *, currency: str | None = None, limit: int = 400) -> dict[str, Any]:
    """Adds every numeric leaf of `data` to the store under `prefix` and returns the keys added
    with their value, so the tool result can list exactly which references exist. List items are
    keyed by their id (`buyers.buyer_tn_01.sold_kg`), never by position."""
    added: dict[str, Any] = {}

    def walk(node: Any, path: str) -> None:
        if len(added) >= limit:
            return
        if isinstance(node, bool) or node is None:
            return
        if isinstance(node, (int, float)):
            if math.isfinite(float(node)):
                key = store.add(path, float(node), currency=currency)
                added[key] = node
            return
        if isinstance(node, Mapping):
            for k, v in node.items():
                walk(v, f"{path}.{re.sub(r'[^A-Za-z0-9_\-]', '_', str(k))}")
        elif isinstance(node, (list, tuple)):
            for i, item in enumerate(node):
                walk(item, f"{path}.{_segment(item, i)}" if isinstance(item, Mapping) else f"{path}.{i}")

    walk(data, prefix)
    return added


def numbers_in(values: Iterable[Any]) -> list[float]:
    """All numeric leaves of nested JSON values."""
    out: list[float] = []

    def walk(node: Any) -> None:
        if isinstance(node, bool) or node is None:
            return
        if isinstance(node, (int, float)):
            if math.isfinite(float(node)):
                out.append(float(node))
        elif isinstance(node, Mapping):
            for v in node.values():
                walk(v)
        elif isinstance(node, (list, tuple)):
            for v in node:
                walk(v)

    for value in values:
        walk(value)
    return out
