"""Insight rule protocol (plan §16).

A rule is a pure function `evaluate(ctx) -> list[InsightCandidate]` over a RuleContext (the run,
its input, its constraints and, when computed, its sensitivity) and the thresholds. The message
is a template whose parameters are the evidence; `render` fills it deterministically.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..analytics.context import RunContext
from ..domain.enums import InsightCategory, Severity
from ..domain.insight import Evidence, EvidenceMetric, EvidenceThreshold, InsightCandidate
from .thresholds import Thresholds


@dataclass(frozen=True)
class RuleContext:
    run: RunContext
    thresholds: Thresholds


@dataclass(frozen=True)
class InsightRule:
    id: str
    version: int
    category: InsightCategory
    message: str  # template, formatted with message_params
    evaluate: Callable[[RuleContext], list[InsightCandidate]]


def metric(key: str, value: float | int | str | None, unit: str, source: str) -> EvidenceMetric:
    return EvidenceMetric(key=key, value=value, unit=unit, source=source)


def candidate(
    rule: InsightRule,
    ctx: RuleContext,
    *,
    severity: Severity,
    metrics: list[EvidenceMetric],
    formula_id: str,
    params: dict[str, Any],
    thresholds: dict[str, float] | None = None,
    entity: dict[str, str] | None = None,
    suggested_changes: list[dict[str, Any]] | None = None,
) -> InsightCandidate:
    return InsightCandidate(
        rule_id=rule.id,
        rule_version=rule.version,
        category=rule.category,
        severity=severity,
        entity_ref=entity,
        evidence=Evidence(
            metrics=metrics,
            thresholds=[EvidenceThreshold(key=k, value=v) for k, v in (thresholds or {}).items()],
            entities=[entity] if entity else [],
            formula_id=formula_id,
            run_id=ctx.run.run_id,
            rule_version=rule.version,
        ),
        message_key=f"insight.{rule.id.lower()}",
        message_params=params,
        suggested_changes=suggested_changes or [],
    )


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:,.2f}".rstrip("0").rstrip(".") if abs(value) < 1e6 else f"{value:,.0f}"
    return str(value)


def render(template: str, params: dict[str, Any]) -> str:
    return template.format(**{k: _fmt(v) for k, v in params.items()})
