"""Evaluation metrics schemas."""

from typing import Any, Optional

from pydantic import BaseModel


class EvaluationRunRequest(BaseModel):
    dataset_id: int
    split: str = "test"
    model_run_ids: list[int] = []
    ml_policy: str = "any"


class EvalIdEntry(BaseModel):
    detector: str
    eval_id: int


class EvaluationRunResponse(BaseModel):
    eval_ids: list[EvalIdEntry]


class EvaluationDetailResponse(BaseModel):
    eval_id: int
    dataset_id: int
    detector: str
    split: str
    ml_policy: Optional[str] = None
    n_cases: int
    base_rate: Optional[float] = None
    tp: int
    fp: int
    tn: int
    fn: int
    fpr_valid_variation: Optional[float] = None
    roc_auc: Optional[float] = None
    pr_auc: Optional[float] = None
    latency_ms_median: Optional[float] = None
    latency_ms_p95: Optional[float] = None
    type_metrics: list[dict[str, Any]] = []
