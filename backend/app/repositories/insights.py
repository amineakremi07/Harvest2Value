"""Insights generated for a run."""

from __future__ import annotations

from sqlalchemy import case, delete, select
from sqlalchemy.orm import Session

from ..db.models import Insight

_SEVERITY_ORDER = case({"critical": 0, "warning": 1, "info": 2}, value=Insight.severity, else_=3)


class InsightRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, insight_id: str) -> Insight | None:
        return self.session.get(Insight, insight_id)

    def for_run(self, run_id: str, *, include_dismissed: bool = False) -> list[Insight]:
        query = select(Insight).where(Insight.run_id == run_id)
        if not include_dismissed:
            query = query.where(Insight.dismissed.is_(False))
        return list(self.session.scalars(query.order_by(_SEVERITY_ORDER, Insight.rule_id, Insight.id)).all())

    def replace_for_run(self, run_id: str, insights: list[Insight]) -> None:
        self.session.execute(delete(Insight).where(Insight.run_id == run_id))
        self.session.add_all(insights)
        self.session.flush()
