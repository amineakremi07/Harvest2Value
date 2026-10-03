"""Guard rails around the LLM.

- Untrusted text (dataset names, imported files, conversation history, tool data) is data, never
  instructions: it is passed inside JSON tool results, control characters are stripped, length is
  capped and instruction-like content is flagged and neutralized.
- The model can only call registered tools; there is no shell, file, network or secret access.
- Proposal tools (create_scenario, run_optimization, generate_report) only create *pending*
  actions, and only when the user's own message asks for a change (rule R6: a number in a
  question never creates a modification). Numeric values of a proposal must come from the user.
- Answers are scrubbed of anything that looks like a credential before being stored or shown.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from typing import Any

MAX_USER_MESSAGE = 4000
MAX_UNTRUSTED_STRING = 300
MAX_TOOL_RESULT_CHARS = 7000

_CONTROL = re.compile(r"[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f​-‏‪-‮⁠-⁤]")

# Phrases that try to steer the model, in French and English (lowercased, accents removed).
_INJECTION = re.compile(
    r"(ignore[sz]?|oublie[sz]?|disregard|forget)\s+(all\s+|toutes?\s+|tous\s+|les\s+|the\s+|tes\s+|vos\s+|mes\s+|ces\s+|your\s+|my\s+|these\s+|previous\s+|precedentes?\s+|prior\s+|above\s+)*"
    r"(instructions?|consignes?|regles?|rules|prompts?)"
    r"|system\s*prompt|prompt\s*systeme|you\s+are\s+now|tu\s+es\s+(maintenant|desormais)|act\s+as\s+|"
    r"new\s+instructions?|nouvelles?\s+instructions?|developer\s+mode|jailbreak|"
    r"<\s*/?\s*(system|assistant|tool|instructions?)\s*>|\[\s*(system|inst)\s*\]|"
    r"(call|appelle|execute|run)\s+(the\s+|l')?(tool|outil)|create_scenario|run_optimization|generate_report|"
    r"(reveal|affiche|donne|print|show)\s+.{0,20}(api[\s_-]?key|cle|secret|password|mot\s+de\s+passe|token)",
    re.IGNORECASE,
)

_SECRET = re.compile(
    r"(gsk_[A-Za-z0-9]{20,}|nvapi-[A-Za-z0-9_\-]{20,}|sk-[A-Za-z0-9]{20,}|"
    r"(?:LLM_API_KEY|GROQ_API_KEY|NIM_API_KEY|API_KEY)\s*[=:]\s*\S+|Bearer\s+[A-Za-z0-9._\-]{20,})"
)

# A request to change, simulate or run something (FR/EN). Questions about the data do not match.
_INTENT = re.compile(
    r"\b(cr[eé]{1,2}[ezr]?|cr[eé]ation|ajoute[rsz]?|applique[rsz]?|lance[rsz]?|relance[rsz]?|ex[eé]cute[rsz]?|"
    r"simule[rsz]?|simulation|teste[rsz]?|essaie[rsz]?|essaye[rsz]?|propose[rsz]?|g[eé]n[eè]re[rsz]?|"
    r"fais|faites|optimise[rsz]?|r[eé]optimise[rsz]?|"
    r"create|add|apply|launch|run|rerun|simulate|try|test|propose|generate|make|build|optimi[sz]e|what\s+if|et\s+si)\b",
    re.IGNORECASE,
)


def _fold(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)).lower()


def clean_text(text: str, limit: int) -> str:
    return _CONTROL.sub("", text)[:limit]


def looks_like_injection(text: str) -> bool:
    return bool(_INJECTION.search(_fold(text)))


def neutralize(text: str) -> str:
    """Untrusted string as it may appear in a tool result."""
    cleaned = clean_text(text, MAX_UNTRUSTED_STRING)
    if looks_like_injection(cleaned):
        return "[texte non fiable masqué]"
    return cleaned


def sanitize_untrusted(value: Any) -> tuple[Any, bool]:
    """Deep-cleans data from the database before it reaches the model. Returns the cleaned value
    and whether instruction-like content was found (and masked)."""
    flagged = False

    def walk(node: Any) -> Any:
        nonlocal flagged
        if isinstance(node, str):
            cleaned = neutralize(node)
            flagged = flagged or cleaned != clean_text(node, MAX_UNTRUSTED_STRING)
            return cleaned
        if isinstance(node, dict):
            return {str(k)[:80]: walk(v) for k, v in node.items()}
        if isinstance(node, (list, tuple)):
            return [walk(v) for v in node]
        return node

    return walk(value), flagged


def check_user_message(text: str) -> str:
    cleaned = clean_text(text, MAX_USER_MESSAGE).strip()
    if not cleaned:
        raise ValueError("empty message")
    return cleaned


def history_message(text: str) -> str:
    """Earlier turns are replayed as plain text, with instruction-like content neutralized."""
    cleaned = clean_text(text, 1500)
    return "[message antérieur masqué]" if looks_like_injection(cleaned) else cleaned


def user_asks_for_change(text: str) -> bool:
    """R6: proposals require an explicit request. A plain question, even with a number, is not one."""
    return bool(_INTENT.search(text))


def redact_secrets(text: str) -> str:
    return _SECRET.sub("[secret masqué]", text)


def ungrounded_numbers(values: Iterable[float], allowed: Iterable[float]) -> list[float]:
    """Proposal parameters that the user never typed (sign and display rounding ignored)."""
    allowed_list = [abs(a) for a in allowed]
    missing: list[float] = []
    for value in values:
        v = abs(value)
        if not any(abs(v - a) <= max(1e-9, 0.005 * a) for a in allowed_list):
            missing.append(value)
    return missing


def numeric_params(params: Any) -> list[float]:
    """Numeric leaves of a change's params (booleans excluded)."""
    out: list[float] = []
    if isinstance(params, bool) or params is None:
        return out
    if isinstance(params, (int, float)):
        return [float(params)]
    if isinstance(params, dict):
        for v in params.values():
            out += numeric_params(v)
    elif isinstance(params, list):
        for v in params:
            out += numeric_params(v)
    return out
