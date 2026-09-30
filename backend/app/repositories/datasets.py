"""Datasets and their immutable versions."""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..db.models import Dataset, DatasetVersion


class DatasetRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(
        self,
        workspace_id: str,
        *,
        q: str | None = None,
        archived: bool | None = False,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[tuple[Dataset, DatasetVersion | None]], int]:
        """Datasets with their current version, newest first."""
        query = (
            select(Dataset, DatasetVersion)
            .outerjoin(DatasetVersion, DatasetVersion.id == Dataset.current_version_id)
            .where(Dataset.workspace_id == workspace_id)
        )
        if archived is not None:
            query = query.where(Dataset.archived.is_(archived))
        if q:
            pattern = f"%{q.lower()}%"
            query = query.where(or_(func.lower(Dataset.name).like(pattern), func.lower(Dataset.description).like(pattern)))
        total = self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = self.session.execute(
            query.order_by(Dataset.updated_at.desc(), Dataset.id).offset(offset).limit(limit)
        ).all()
        return [(row[0], row[1]) for row in rows], total

    def get(self, dataset_id: str, workspace_id: str) -> Dataset | None:
        dataset = self.session.get(Dataset, dataset_id)
        if dataset is None or dataset.workspace_id != workspace_id:
            return None
        return dataset

    def add(self, dataset: Dataset) -> None:
        self.session.add(dataset)
        self.session.flush()

    def add_version(self, version: DatasetVersion) -> None:
        self.session.add(version)
        self.session.flush()

    def delete(self, dataset: Dataset) -> None:
        self.session.delete(dataset)
        self.session.flush()

    def get_version(self, dataset_id: str, version_no: int) -> DatasetVersion | None:
        return self.session.scalar(
            select(DatasetVersion).where(
                DatasetVersion.dataset_id == dataset_id, DatasetVersion.version_no == version_no
            )
        )

    def get_version_by_id(self, version_id: str) -> DatasetVersion | None:
        return self.session.get(DatasetVersion, version_id)

    def latest_version_no(self, dataset_id: str) -> int:
        return self.session.scalar(
            select(func.coalesce(func.max(DatasetVersion.version_no), 0)).where(DatasetVersion.dataset_id == dataset_id)
        ) or 0

    def list_versions(self, dataset_id: str, *, offset: int = 0, limit: int = 20) -> tuple[list[DatasetVersion], int]:
        query = select(DatasetVersion).where(DatasetVersion.dataset_id == dataset_id)
        total = self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
        versions = self.session.scalars(query.order_by(DatasetVersion.version_no.desc()).offset(offset).limit(limit)).all()
        return list(versions), total
