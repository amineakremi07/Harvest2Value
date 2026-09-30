"""Scenarios and their ordered changes."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db.models import Scenario, ScenarioChange


class ScenarioRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, scenario: Scenario) -> None:
        self.session.add(scenario)
        self.session.flush()

    def get(self, scenario_id: str, workspace_id: str) -> Scenario | None:
        scenario = self.session.get(Scenario, scenario_id)
        if scenario is None or scenario.workspace_id != workspace_id:
            return None
        return scenario

    def list(
        self,
        workspace_id: str,
        *,
        dataset_id: str | None = None,
        status: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Scenario], int]:
        query = select(Scenario).where(Scenario.workspace_id == workspace_id)
        if dataset_id is not None:
            query = query.where(Scenario.dataset_id == dataset_id)
        if status is not None:
            query = query.where(Scenario.status == status)
        total = self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = self.session.scalars(query.order_by(Scenario.updated_at.desc(), Scenario.id).offset(offset).limit(limit)).all()
        return list(rows), total

    def for_dataset(self, dataset_id: str) -> list[Scenario]:
        return list(self.session.scalars(select(Scenario).where(Scenario.dataset_id == dataset_id)).all())

    def children(self, scenario_id: str) -> list[Scenario]:
        return list(self.session.scalars(select(Scenario).where(Scenario.parent_id == scenario_id)).all())

    def delete(self, scenario: Scenario) -> None:
        self.session.delete(scenario)
        self.session.flush()

    # ---- changes ----

    def changes(self, scenario_id: str) -> list[ScenarioChange]:
        return list(
            self.session.scalars(
                select(ScenarioChange).where(ScenarioChange.scenario_id == scenario_id).order_by(ScenarioChange.position)
            ).all()
        )

    def get_change(self, scenario_id: str, change_id: str) -> ScenarioChange | None:
        change = self.session.get(ScenarioChange, change_id)
        if change is None or change.scenario_id != scenario_id:
            return None
        return change

    def add_change(self, change: ScenarioChange) -> None:
        self.session.add(change)
        self.session.flush()

    def delete_change(self, change: ScenarioChange) -> None:
        self.session.delete(change)
        self.session.flush()

    def set_order(self, changes: list[ScenarioChange]) -> None:
        """Renumber 0..n-1 in the given order. Two passes because (scenario_id, position) is unique."""
        for offset, change in enumerate(changes):
            change.position = -1 - offset
        self.session.flush()
        for position, change in enumerate(changes):
            change.position = position
        self.session.flush()
