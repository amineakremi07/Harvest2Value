"""InsightEngine: run every rule on a run context, most severe first."""

from __future__ import annotations

from collections.abc import Sequence

from ..analytics.context import RunContext
from ..domain.insight import InsightCandidate
from .base import InsightRule, RuleContext, render
from .rules import ALL_RULES, RULES_BY_ID
from .thresholds import DEFAULT_THRESHOLDS, Thresholds

SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


class InsightEngine:
    def __init__(self, rules: Sequence[InsightRule] = ALL_RULES, thresholds: Thresholds = DEFAULT_THRESHOLDS) -> None:
        self.rules = list(rules)
        self.thresholds = thresholds

    def evaluate(self, run: RunContext) -> list[InsightCandidate]:
        ctx = RuleContext(run=run, thresholds=self.thresholds)
        found = [c for rule in self.rules for c in rule.evaluate(ctx)]
        return sorted(found, key=lambda c: (SEVERITY_ORDER[c.severity], c.rule_id, str(c.entity_ref)))


def message_for(rule_id: str, params: dict[str, object]) -> str:
    rule = RULES_BY_ID.get(rule_id)
    return render(rule.message, params) if rule else rule_id
