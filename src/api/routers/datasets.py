"""Dataset management and ingestion router."""

import io
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from src.api.schemas.common import PaginatedResponse, PaginationMeta
from src.api.schemas.datasets import (
    CaseDetailResponse,
    CaseResponse,
    DatasetResponse,
    EventSchema,
    GenerateDatasetRequest,
)
from src.db.repositories.dataset_repo import DatasetRepository
from src.db.session import get_db
from src.workflow_ml.injector import AnomalyInjector
from src.workflow_ml.sequences import build_traces
from src.workflow_ml.simulator import WorkflowSimulator, load_simulator_config
from src.workflow_ml.splits import split_cases

router = APIRouter(tags=["Datasets"])


@router.post("/datasets/generate", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
def generate_dataset_endpoint(
    payload: GenerateDatasetRequest,
    db: Session = Depends(get_db),
) -> DatasetResponse:
    """Generate a seeded synthetic dataset and persist cases & event logs."""
    config_path = Path("config/simulator.yaml")
    cfg = dict(load_simulator_config(config_path)) if config_path.exists() else {}

    total_cases = payload.n_train + payload.n_val + payload.n_test
    if total_cases > 0:
        splits_cfg = dict(cfg.get("splits", {}))
        splits_cfg["train"] = payload.n_train / total_cases
        splits_cfg["val"] = payload.n_val / total_cases
        splits_cfg["test"] = payload.n_test / total_cases
        cfg["splits"] = splits_cfg

    simulator = WorkflowSimulator(config=cfg, seed=payload.seed)
    raw_cases = simulator.generate_dataset(n_cases=total_cases)

    injector = AnomalyInjector(config=cfg, seed=payload.seed)
    cases = injector.inject_anomalies(raw_cases)

    split_map = split_cases(cases, config=cfg, seed=payload.seed)

    repo = DatasetRepository(db)
    ds = repo.create_dataset(
        workflow_id=payload.workflow_id,
        name=payload.name,
        source_kind="synthetic",
        label_semantics="injected",
        seed=payload.seed,
        config_hash="sim_v1",
    )

    for c in cases:
        cid = c.trace.case_id
        assigned_split = split_map.get(cid, "train")
        case_obj = repo.add_case(
            dataset_id=ds.dataset_id,
            case_id=cid,
            label_class=c.label_class,
            anomaly_type=c.anomaly_type,
            split=assigned_split,
        )
        repo.add_events(case_obj.case_pk, c.trace.events)

    return DatasetResponse(
        dataset_id=ds.dataset_id,
        workflow_id=ds.workflow_id,
        name=ds.name,
        source_kind=ds.source_kind,
        label_semantics=ds.label_semantics,
        seed=ds.seed,
        config_hash=ds.config_hash,
        n_cases=len(cases),
        created_at=ds.created_at,
    )


@router.post("/datasets/upload", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
def upload_dataset(
    workflow_id: int = Form(...),
    name: str = Form(...),
    source_kind: str = Form("uploaded"),
    events_file: UploadFile = File(...),
    labels_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
) -> DatasetResponse:
    """Upload CSV events log (+ optional labels CSV) and ingest as a dataset."""
    events_bytes = events_file.file.read()
    events_df = pd.read_csv(io.BytesIO(events_bytes))

    labels_map = {}
    if labels_file:
        labels_bytes = labels_file.file.read()
        labels_df = pd.read_csv(io.BytesIO(labels_bytes))
        for _, row in labels_df.iterrows():
            cid = str(row["case_id"])
            labels_map[cid] = {
                "label_class": str(row.get("label_class", "normal")),
                "anomaly_type": str(row.get("anomaly_type", "")) if pd.notna(row.get("anomaly_type")) else None,
                "split": str(row.get("split", "test")) if pd.notna(row.get("split")) else "test",
            }

    traces, _ = build_traces(events_df)
    repo = DatasetRepository(db)
    ds = repo.create_dataset(
        workflow_id=workflow_id,
        name=name,
        source_kind=source_kind,
        label_semantics="external" if labels_file else "none",
        seed=None,
        config_hash=None,
    )

    for tr in traces:
        cid = tr.case_id
        meta = labels_map.get(cid, {"label_class": None, "anomaly_type": None, "split": "test"})
        c_obj = repo.add_case(
            dataset_id=ds.dataset_id,
            case_id=cid,
            label_class=meta["label_class"],
            anomaly_type=meta["anomaly_type"],
            split=meta["split"],
        )
        repo.add_events(c_obj.case_pk, tr.events)

    return DatasetResponse(
        dataset_id=ds.dataset_id,
        workflow_id=ds.workflow_id,
        name=ds.name,
        source_kind=ds.source_kind,
        label_semantics=ds.label_semantics,
        seed=ds.seed,
        config_hash=ds.config_hash,
        n_cases=len(traces),
        created_at=ds.created_at,
    )


@router.get("/datasets", response_model=list[DatasetResponse])
def list_datasets(db: Session = Depends(get_db)) -> list[DatasetResponse]:
    """List all registered datasets."""
    repo = DatasetRepository(db)
    datasets = repo.list_datasets()
    results = []
    for d in datasets:
        results.append(
            DatasetResponse(
                dataset_id=d.dataset_id,
                workflow_id=d.workflow_id,
                name=d.name,
                source_kind=d.source_kind,
                label_semantics=d.label_semantics,
                seed=d.seed,
                config_hash=d.config_hash,
                n_cases=len(d.cases),
                created_at=d.created_at,
            )
        )
    return results


@router.get("/datasets/{id}", response_model=DatasetResponse)
def get_dataset(id: int, db: Session = Depends(get_db)) -> DatasetResponse:
    """Retrieve metadata for a specific dataset."""
    repo = DatasetRepository(db)
    d = repo.get_dataset(id)
    if not d:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "DATASET_NOT_FOUND", "message": f"Dataset {id} not found"},
        )
    return DatasetResponse(
        dataset_id=d.dataset_id,
        workflow_id=d.workflow_id,
        name=d.name,
        source_kind=d.source_kind,
        label_semantics=d.label_semantics,
        seed=d.seed,
        config_hash=d.config_hash,
        n_cases=len(d.cases),
        created_at=d.created_at,
    )


@router.get("/datasets/{id}/cases", response_model=PaginatedResponse[CaseResponse])
def get_dataset_cases(
    id: int,
    label_class: Optional[str] = Query(None),
    split: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> PaginatedResponse[CaseResponse]:
    """Retrieve paginated list of cases belonging to a dataset."""
    repo = DatasetRepository(db)
    d = repo.get_dataset(id)
    if not d:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "DATASET_NOT_FOUND", "message": f"Dataset {id} not found"},
        )

    cases, total = repo.list_cases(
        dataset_id=id,
        label_class=label_class,
        split=split,
        page=page,
        page_size=page_size,
    )

    items = [
        CaseResponse(
            case_pk=c.case_pk,
            dataset_id=c.dataset_id,
            case_id=c.case_id,
            label_class=c.label_class,
            anomaly_type=c.anomaly_type,
            split=c.split,
            n_events=len(c.events),
        )
        for c in cases
    ]
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return PaginatedResponse(
        items=items,
        pagination=PaginationMeta(
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=total_pages,
        ),
    )


@router.get("/cases/{case_pk}", response_model=CaseDetailResponse)
def get_case_detail(case_pk: int, db: Session = Depends(get_db)) -> CaseDetailResponse:
    """Retrieve full event log for a single case."""
    repo = DatasetRepository(db)
    c = repo.get_case_by_pk(case_pk)
    if not c:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CASE_NOT_FOUND", "message": f"Case with pk {case_pk} not found"},
        )

    events = [
        EventSchema(
            seq_index=e.seq_index,
            activity=e.activity,
            ts=e.ts,
            attributes=e.attributes,
        )
        for e in sorted(c.events, key=lambda x: x.seq_index)
    ]

    return CaseDetailResponse(
        case_pk=c.case_pk,
        dataset_id=c.dataset_id,
        case_id=c.case_id,
        label_class=c.label_class,
        anomaly_type=c.anomaly_type,
        split=c.split,
        events=events,
    )
