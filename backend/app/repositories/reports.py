"""Frozen reports."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db.models import Report


class ReportRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, report_id: str, workspace_id: str) -> Report | None:
        row = self.session.get(Report, report_id)
        return row if row is not None and row.workspace_id == workspace_id else None

    def list(self, workspace_id: str, *, run_id: str | None, page: int, page_size: int) -> tuple[list[Report], int]:
        query = select(Report).where(Report.workspace_id == workspace_id)
        if run_id:
            query = query.where(Report.run_id == run_id)
        total = self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = self.session.scalars(query.order_by(Report.created_at.desc(), Report.id).offset((page - 1) * page_size).limit(page_size)).all()
        return list(rows), total

    def add(self, report: Report) -> Report:
        self.session.add(report)
        self.session.flush()
        return report

    def delete(self, report: Report) -> None:
        self.session.delete(report)
        self.session.flush()
