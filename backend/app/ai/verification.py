"""NumericVerifier: every number in an assistant answer must come from the backend.

A number is verified when it is a `{{ref:...}}` the backend knows, or when a raw number written
by the model matches (within display rounding) a value the backend produced in this conversation
(tool results) or a number the user typed. French and English formats are both understood
(`29 174,84`, `29,174.84`, `1.500`, `12 %`). Anything else is reported; the copilot regenerates
once with feedback, then marks what is still unverified (⟦?…⟧) instead of hiding it.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

from .context import RefStore
from .rendering import REF_PATTERN, UNVERIFIED_CLOSE, UNVERIFIED_OPEN

_SPACES = "   "
# A number, optionally grouped by thousands (space, nbsp, narrow nbsp, comma or point), with
# an optional decimal part. Look-arounds keep identifiers (r2, J5, buyer_tn_01, v2) out.
NUMBER = re.compile(
    r"(?<![\w.,\-])(?<![\w][\-])"
    r"(?P<num>[-−+]?\d{1,3}(?:[   .,]\d{3})+(?:[.,]\d+)?|[-−+]?\d+(?:[.,]\d+)?)"
    r"(?![\w]|[.,]\d)"
)
_LIST_MARKER = re.compile(r"^\s*\d{1,2}[.)]\s")


@dataclass(frozen=True)
class Candidate:
    value: float
    decimals: int


def interpretations(raw: str) -> list[Candidate]:
    """Every plausible numeric reading of `raw` (French and English conventions)."""
    text = raw.replace("−", "-").replace("+", "")
    sign = -1.0 if text.startswith("-") else 1.0
    text = text.lstrip("-")
    out: list[Candidate] = []

    def add(integer: str, frac: str) -> None:
        try:
            value = sign * float(f"{integer}.{frac}" if frac else integer)
        except ValueError:
            return
        candidate = Candidate(value, len(frac))
        if candidate not in out:
            out.append(candidate)

    for space in _SPACES:
        text = text.replace(space, " ")
    if " " in text:  # French grouping: "29 174,84" / "12 000"
        integer, _, frac = text.replace(" ", "").partition(",")
        if "." in integer:  # "29 174.84" (mixed) -> English decimal
            integer, _, frac = integer.partition(".")
        add(integer, frac)
        return out
    commas, points = text.count(","), text.count(".")
    if commas and points:  # "29,174.84" (EN) or "29.174,84" (FR)
        if text.rfind(".") > text.rfind(","):
            integer, _, frac = text.replace(",", "").partition(".")
        else:
            integer, _, frac = text.replace(".", "").partition(",")
        add(integer, frac)
    elif commas == 1 or points == 1:
        sep = "," if commas else "."
        integer, _, frac = text.partition(sep)
        add(integer, frac)  # decimal reading: 1,5 / 1.5
        if len(frac) == 3:
            add(integer + frac, "")  # thousands reading: 1,500 / 1.500
    elif commas > 1 or points > 1:
        add(text.replace(",", "").replace(".", ""), "")
    else:
        add(text, "")
    return out


def _matches(candidate: Candidate, known: float) -> bool:
    tolerance = max(0.5 * 10 ** (-candidate.decimals), 0.005 * abs(known), 1e-9)
    return bool(abs(candidate.value - known) <= tolerance or abs(abs(candidate.value) - abs(known)) <= tolerance)


@dataclass
class RawNumber:
    text: str
    start: int
    end: int


def raw_numbers(text: str) -> list[RawNumber]:
    """Numbers written as digits in `text`, outside `{{ref:...}}` placeholders and list markers."""
    masked = REF_PATTERN.sub(lambda m: " " * len(m.group(0)), text)
    masked = re.sub(r"⟦\?[^⟧]*⟧", lambda m: " " * len(m.group(0)), masked)
    found: list[RawNumber] = []
    line_starts = {0} | {m.end() for m in re.finditer(r"\n", masked)}
    for match in NUMBER.finditer(masked):
        start = match.start("num")
        line_start = max(s for s in line_starts if s <= start)
        if start == line_start + (len(masked[line_start:start]) - len(masked[line_start:start].lstrip())) and _LIST_MARKER.match(masked[line_start:]):
            continue  # "1. " / "2) " list numbering
        found.append(RawNumber(match.group("num"), start, match.end("num")))
    return found


@dataclass
class VerificationReport:
    unknown_refs: list[str] = field(default_factory=list)
    unverified: list[str] = field(default_factory=list)
    checked: int = 0
    regenerated: bool = False

    @property
    def ok(self) -> bool:
        return not self.unknown_refs and not self.unverified

    def feedback(self) -> str:
        parts = []
        if self.unknown_refs:
            parts.append("These references do not exist: " + ", ".join(self.unknown_refs) + ".")
        if self.unverified:
            parts.append("These numbers do not come from a tool result: " + ", ".join(self.unverified) + ".")
        parts.append(
            "Rewrite the answer. Write every number as {{ref:KEY}} using only keys listed in the tool results' "
            "`refs`, or call a tool to get it. Do not write units or currency after a reference."
        )
        return " ".join(parts)

    def to_json(self) -> dict[str, object]:
        return {
            "status": "verified" if self.ok else "unverified",
            "unknown_refs": self.unknown_refs,
            "unverified_numbers": self.unverified,
            "checked_numbers": self.checked,
            "regenerated": self.regenerated,
        }


class NumericVerifier:
    def __init__(self, refs: RefStore, known_numbers: Iterable[float] = (), user_numbers: Iterable[float] = ()) -> None:
        self.refs = refs
        self.known = [*refs.numbers(), *known_numbers, *user_numbers]

    def is_known(self, raw: str) -> bool:
        return any(_matches(c, k) for c in interpretations(raw) for k in self.known)

    def verify(self, text: str) -> VerificationReport:
        report = VerificationReport()
        for match in REF_PATTERN.finditer(text):
            report.checked += 1
            if match.group(1) not in self.refs and match.group(1) not in report.unknown_refs:
                report.unknown_refs.append(match.group(1))
        for number in raw_numbers(text):
            report.checked += 1
            if not self.is_known(number.text) and number.text not in report.unverified:
                report.unverified.append(number.text)
        return report

    def mark(self, rendered: str) -> str:
        """Wraps every raw number of the rendered answer that is not known in ⟦?…⟧."""
        pieces: list[str] = []
        last = 0
        for number in raw_numbers(rendered):
            if self.is_known(number.text):
                continue
            pieces += [rendered[last : number.start], f"{UNVERIFIED_OPEN}{number.text}{UNVERIFIED_CLOSE}"]
            last = number.end
        pieces.append(rendered[last:])
        return "".join(pieces)


def numbers_in_text(text: str) -> list[float]:
    """Every reading of every number the user typed (they may be quoted back)."""
    return [c.value for n in raw_numbers(text) for c in interpretations(n.text)]
