"""Dataset and Case schemas."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class GenerateDatasetRequest(BaseModel):
    workflow_id: int
    name: str = "Synthetic Dataset"
    seed: int = 42
    n_train: int = 800
    n_val: int = 100
    n_test: int = 100
    anomaly_rate: float = Field(0.15, ge=0.0, le=1.0)


class DatasetResponse(BaseModel):
    dataset_id: int
    workflow_id: int
    name: str
    source_kind: str
    label_semantics: str
    seed: Optional[int] = None
    config_hash: Optional[str] = None
    n_cases: int = 0
    created_at: datetime


class CaseResponse(BaseModel):
    case_pk: int
    dataset_id: int
    case_id: str
    label_class: Optional[str] = None
    anomaly_type: Optional[str] = None
    split: Optional[str] = None
    n_events: int = 0


class EventSchema(BaseModel):
    seq_index: int
    activity: str
    ts: datetime
    attributes: dict[str, Any] = {}


class CaseDetailResponse(BaseModel):
    case_pk: int
    dataset_id: int
    case_id: str
    label_class: Optional[str] = None
    anomaly_type: Optional[str] = None
    split: Optional[str] = None
    events: list[EventSchema]
