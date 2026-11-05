from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.common.types import Event, Trace
from src.db.models import Case, Dataset, EventLog


class DatasetRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_dataset(
        self,
        workflow_id: int,
        name: str,
        source_kind: str,
        label_semantics: str,
        seed: int | None = None,
        config_hash: str | None = None,
    ) -> Dataset:
        dataset = Dataset(
            workflow_id=workflow_id,
            name=name,
            source_kind=source_kind,
            label_semantics=label_semantics,
            seed=seed,
            config_hash=config_hash,
        )
        self.db.add(dataset)
        self.db.commit()
        self.db.refresh(dataset)
        return dataset

    def get_dataset(self, dataset_id: int) -> Dataset | None:
        stmt = select(Dataset).where(Dataset.dataset_id == dataset_id)
        return self.db.scalars(stmt).first()

    def list_datasets(self) -> list[Dataset]:
        stmt = select(Dataset).order_by(Dataset.dataset_id)
        return list(self.db.scalars(stmt).all())

    def add_case(
        self,
        dataset_id: int,
        case_id: str,
        label_class: str | None = None,
        anomaly_type: str | None = None,
        split: str | None = None,
    ) -> Case:
        c = Case(
            dataset_id=dataset_id,
            case_id=case_id,
            label_class=label_class,
            anomaly_type=anomaly_type,
            split=split,
        )
        self.db.add(c)
        self.db.commit()
        self.db.refresh(c)
        return c

    def get_case(self, dataset_id: int, case_id: str) -> Case | None:
        stmt = select(Case).where(Case.dataset_id == dataset_id, Case.case_id == case_id)
        return self.db.scalars(stmt).first()

    def get_case_by_pk(self, case_pk: int) -> Case | None:
        stmt = select(Case).where(Case.case_pk == case_pk)
        return self.db.scalars(stmt).first()

    def list_cases(
        self,
        dataset_id: int,
        label_class: str | None = None,
        split: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Case], int]:
        stmt = select(Case).where(Case.dataset_id == dataset_id)
        if label_class:
            stmt = stmt.where(Case.label_class == label_class)
        if split:
            stmt = stmt.where(Case.split == split)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.scalar(count_stmt) or 0

        offset = (page - 1) * page_size
        stmt = stmt.order_by(Case.case_pk).offset(offset).limit(page_size)
        items = list(self.db.scalars(stmt).all())
        return items, total

    def add_events(self, case_pk: int, events: Sequence[Event]) -> list[EventLog]:
        logs: list[EventLog] = []
        for i, e in enumerate(events):
            log = EventLog(
                case_pk=case_pk,
                seq_index=i,
                activity=e.activity,
                ts=e.timestamp,
                attributes=e.attributes or {},
            )
            self.db.add(log)
            logs.append(log)
        self.db.commit()
        return logs

    def get_traces_for_dataset(
        self,
        dataset_id: int,
        split: str | None = None,
    ) -> list[Trace]:
        stmt = select(Case).where(Case.dataset_id == dataset_id)
        if split:
            stmt = stmt.where(Case.split == split)
        stmt = stmt.order_by(Case.case_pk)
        cases = list(self.db.scalars(stmt).all())

        traces: list[Trace] = []
        for c in cases:
            ev_stmt = (
                select(EventLog).where(EventLog.case_pk == c.case_pk).order_by(EventLog.seq_index)
            )
            event_records = list(self.db.scalars(ev_stmt).all())
            domain_events = [
                Event(
                    case_id=c.case_id,
                    activity=er.activity,
                    timestamp=er.ts,
                    attributes=er.attributes,
                )
                for er in event_records
            ]
            traces.append(Trace(case_id=c.case_id, events=domain_events))
        return traces
