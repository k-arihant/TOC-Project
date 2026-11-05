"""Machine Learning model schemas."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class TrainModelRequest(BaseModel):
    dataset_id: int
    detector: str = Field("isolation_forest", description="'isolation_forest'|'markov'|'kmeans'|'random_forest'")
    params: dict[str, Any] = {}
    seed: int = 0
    target_fpr: float = Field(0.05, ge=0.0, le=1.0)


class TrainModelResponse(BaseModel):
    model_run_id: int
    detector: str
    threshold: float
    feature_spec_version: str = "v1"
    n_train_cases: int


class ModelRunResponse(BaseModel):
    model_run_id: int
    dataset_id: int
    detector: str
    params: dict[str, Any]
    feature_spec_version: Optional[str] = None
    seed: int
    target_fpr: Optional[float] = None
    threshold: Optional[float] = None
    created_at: datetime


class ScoreDatasetRequest(BaseModel):
    dataset_id: int
    model_run_id: int
    split: str = "test"


class ScoreDatasetResponse(BaseModel):
    dataset_id: int
    model_run_id: int
    split: str
    n_scored: int
    n_anomalies: int


class ModelMetricsResponse(BaseModel):
    model_run_id: int
    detector: str
    roc_points: list[dict[str, float]] = []
    pr_points: list[dict[str, float]] = []
    score_histogram: dict[str, list[float]] = {}
    roc_auc: Optional[float] = None
    pr_auc: Optional[float] = None
