"""Turns `{{ref:key}}` placeholders into numbers formatted by the backend.

Unknown references are never guessed: they are rendered as an explicit unverified marker
(`⟦?⟧` with the key), which the verifier reports and the frontend highlights.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from .context import RefStore, RefValue

REF_PATTERN = re.compile(r"\{\{\s*ref\s*:\s*([^}\s]+)\s*\}\}")
# Rendered text marks anything the backend could not verify: ⟦?…⟧. The frontend parses it.
UNVERIFIED_OPEN = "⟦?"
UNVERIFIED_CLOSE = "⟧"

Locale = Literal["fr", "en"]

_UNIT_TEXT: dict[str, dict[Locale, str]] = {
    "kg": {"fr": "kg", "en": "kg"},
    "%": {"fr": "%", "en": "%"},
    "days": {"fr": "j", "en": "days"},
    "trips": {"fr": "trajets", "en": "trips"},
    "hours": {"fr": "h", "en": "h"},
    "km": {"fr": "km", "en": "km"},
}


def _group(integer: str, sep: str) -> str:
    out = []
    while len(integer) > 3:
        out.insert(0, integer[-3:])
        integer = integer[:-3]
    out.insert(0, integer)
    return sep.join(out)


def format_number(value: float, decimals: int, locale: Locale = "fr") -> str:
    """French: narrow no-break space thousands and decimal comma; English: comma and point."""
    value = round(value, decimals) + 0.0  # also turns -0.0 into 0.0
    sign = "-" if value < 0 else ""
    text = f"{abs(value):.{decimals}f}"
    integer, _, frac = text.partition(".")
    if locale == "fr":
        grouped = _group(integer, " ")
        return f"{sign}{grouped},{frac}" if frac else f"{sign}{grouped}"
    grouped = _group(integer, ",")
    return f"{sign}{grouped}.{frac}" if frac else f"{sign}{grouped}"


def decimals_for(ref: RefValue) -> int:
    v = abs(ref.value)
    if ref.unit in ("count", "trips", "days"):
        return 0
    if ref.unit == "currency/kg":
        return 2 if v >= 0.1 else 3
    if ref.unit in ("%", "hours"):
        return 1
    if ref.unit == "number":
        return 0 if float(ref.value).is_integer() else 2
    return 0 if v >= 100 else 2


def render_value(ref: RefValue, locale: Locale = "fr", default_currency: str = "TND") -> str:
    number = format_number(ref.value, decimals_for(ref), locale)
    currency = ref.currency or default_currency
    if ref.unit == "currency":
        return f"{number} {currency}"
    if ref.unit == "currency/kg":
        return f"{number} {currency}/kg"
    if ref.unit == "%":
        return f"{number} %" if locale == "fr" else f"{number}%"
    unit = _UNIT_TEXT.get(ref.unit, {}).get(locale)
    return f"{number} {unit}" if unit else number


@dataclass
class Rendered:
    text: str
    used_refs: list[str] = field(default_factory=list)
    unknown_refs: list[str] = field(default_factory=list)


def render(text: str, refs: RefStore, *, locale: Locale = "fr", default_currency: str = "TND") -> Rendered:
    used: list[str] = []
    unknown: list[str] = []

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        ref = refs.get(key)
        if ref is None:
            unknown.append(key)
            return f"{UNVERIFIED_OPEN}{key}{UNVERIFIED_CLOSE}"
        used.append(key)
        return render_value(ref, locale, default_currency)

    return Rendered(REF_PATTERN.sub(replace, text), used, unknown)


def strip_refs(text: str) -> str:
    return REF_PATTERN.sub(" ", text)


def detect_locale(text: str) -> Locale:
    """Cheap language guess for the answer formatting (French by default)."""
    words = set(re.findall(r"[a-zà-ÿ']+", text.lower()))
    english = {"the", "what", "which", "how", "is", "are", "of", "and", "profit", "why", "show", "give", "me", "my"}
    french = {"le", "la", "les", "quel", "quelle", "est", "des", "du", "et", "pourquoi", "combien", "mon", "ma", "de"}
    return "en" if len(words & english) > len(words & french) else "fr"
