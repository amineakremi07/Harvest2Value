"""Real tool-calling probe against the configured LLM provider (phase 11 prerequisite).

Run from backend/:  .venv/Scripts/python scripts/probe_tool_calling.py [model ...] [--repeat N]
Uses LLM_PROVIDER / LLM_API_KEY (or GROQ_API_KEY) from the environment or .env. Only synthetic
data is sent. Prints one line per case and a JSON summary; nothing is written to disk.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai.providers import ChatMessage, ToolSpec  # noqa: E402
from app.ai.providers.factory import get_provider  # noqa: E402
from app.core.config import get_settings  # noqa: E402

TOOLS = [
    ToolSpec(
        name="get_run",
        description="KPIs of an optimization run (realized profit, revenue, waste rate). Use it for any question about a run's numbers.",
        parameters={
            "type": "object",
            "properties": {"run_id": {"type": "string", "description": "Run id, e.g. r2"}},
            "required": ["run_id"],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="get_buyer_analysis",
        description="Per-buyer volumes and net price for a run.",
        parameters={
            "type": "object",
            "properties": {
                "run_id": {"type": "string"},
                "sort_by": {"type": "string", "enum": ["net_revenue", "sold_kg"]},
            },
            "required": ["run_id", "sort_by"],
            "additionalProperties": False,
        },
    ),
]

TOOL_RESULTS: dict[str, dict[str, Any]] = {
    "get_run": {"ref": "r2", "kpis": {"realized_profit": 29174.84, "realized_revenue": 31401.35, "waste_rate_pct": 0.13}},
    "get_buyer_analysis": {"ref": "r2", "buyers": [{"name": "Huilerie Sfax Export", "sold_kg": 3987.96, "net_revenue": 9500.0}]},
}

SYSTEM = (
    "You are the Harvest2Value copilot. Never invent numbers: get them with tools. "
    "When you state a number from a tool result, write a reference instead of the number, "
    "e.g. {{ref:r2.kpis.realized_profit}}. Answer in the user's language."
)

CASES: list[dict[str, Any]] = [
    {"id": "single_tool_fr", "user": "Quel est le profit réalisé de l'exécution r2 ?", "expect_tools": {"get_run"}},
    {"id": "no_tool", "user": "Bonjour, que peux-tu faire pour moi ?", "expect_tools": set()},
    {"id": "enum_arg", "user": "Classe les acheteurs de r2 par volume vendu.", "expect_tools": {"get_buyer_analysis"}},
    {"id": "two_tools_en", "user": "For run r2, give me the profit and the top buyer by net revenue.", "expect_tools": {"get_run", "get_buyer_analysis"}},
]


def validate_args(name: str, raw: str) -> str | None:
    try:
        args = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return "invalid JSON"
    spec = next(t for t in TOOLS if t.name == name).parameters
    missing = [k for k in spec["required"] if k not in args]
    extra = [k for k in args if k not in spec["properties"]]
    bad_enum = [
        k for k, v in args.items() if "enum" in spec["properties"].get(k, {}) and v not in spec["properties"][k]["enum"]
    ]
    problems = [f"missing {missing}" if missing else "", f"extra {extra}" if extra else "", f"bad enum {bad_enum}" if bad_enum else ""]
    return "; ".join(p for p in problems if p) or None


async def run_case(provider: Any, case: dict[str, Any]) -> dict[str, Any]:
    messages = [ChatMessage(role="system", content=SYSTEM), ChatMessage(role="user", content=case["user"])]
    called: list[str] = []
    arg_errors: list[str] = []
    started = time.perf_counter()
    final = None
    for _ in range(4):  # at most 3 tool rounds, then the answer
        reply = await provider.complete(messages, tools=TOOLS, temperature=0.1, max_tokens=1024)
        if not reply.tool_calls:
            final = reply.content or ""
            break
        messages.append(ChatMessage(role="assistant", content=reply.content, tool_calls=reply.tool_calls))
        for call in reply.tool_calls:
            called.append(call.name)
            if call.name not in TOOL_RESULTS:
                arg_errors.append(f"unknown tool {call.name}")
                result: dict[str, Any] = {"error": "unknown tool"}
            else:
                problem = validate_args(call.name, call.arguments)
                if problem:
                    arg_errors.append(f"{call.name}: {problem}")
                result = TOOL_RESULTS[call.name]
            messages.append(ChatMessage(role="tool", tool_call_id=call.id, content=json.dumps(result)))
    elapsed = time.perf_counter() - started
    refs = re.findall(r"\{\{ref:[^}]+\}\}", final or "")
    raw_numbers = [n for n in re.findall(r"\d[\d\s.,]*\d", re.sub(r"\{\{ref:[^}]+\}\}", "", final or "")) if len(n) > 3]
    return {
        "case": case["id"],
        "tools_called": called,
        "tools_ok": set(called) == case["expect_tools"],
        "arg_errors": arg_errors,
        "answered": final is not None,
        "refs": refs,
        "raw_numbers": raw_numbers,
        "seconds": round(elapsed, 2),
        "answer": (final or "")[:160],
    }


async def main(models: list[str], repeat: int) -> None:
    settings = get_settings()
    summary = []
    for model in models or [None]:
        provider = get_provider(settings.model_copy(update={"llm_model": model} if model else {}))
        print(f"== provider={provider.name} model={provider.model}")
        for case in CASES:
            for i in range(repeat):
                try:
                    r = await run_case(provider, case)
                except Exception as exc:  # noqa: BLE001 - a probe reports every failure
                    r = {"case": case["id"], "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
                r["model"] = provider.model
                r["try"] = i + 1
                summary.append(r)
                print(json.dumps(r, ensure_ascii=False))
    ok = [r for r in summary if r.get("tools_ok") and not r.get("arg_errors") and r.get("answered")]
    print(json.dumps({"total": len(summary), "fully_ok": len(ok)}, indent=1))


if __name__ == "__main__":
    args = sys.argv[1:]
    repeat = 1
    if "--repeat" in args:
        i = args.index("--repeat")
        repeat = int(args[i + 1])
        args = args[:i] + args[i + 2 :]
    asyncio.run(main(args, repeat))
