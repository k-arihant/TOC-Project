"""Hybrid detection schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AnalyzeTraceRequest(BaseModel):
    workflow_id: int
    case_id: str = "adhoc-1"
    activities: list[str]
    model_run_ids: list[int] = []
    ml_policy: str = Field("any", description="'any' | 'all' | 'primary:<detector>'")


class FactorSchema(BaseModel):
    name: str
    value: float
    reference: float
    note: str


class MlScoreSchema(BaseModel):
    detector: str
    raw_score: float
    norm_score: float
    threshold: float
    is_anomaly: bool
    factors: list[FactorSchema] = []


class AnalyzeTraceResponse(BaseModel):
    case_id: str
    final_label: str = Field(..., description="'NORMAL'|'RULE_VIOLATION'|'STATISTICAL_ANOMALY'|'IN_PROGRESS'")
    fsm: dict[str, Any]
    ml: list[MlScoreSchema] = []
    explanations: list[str] = []


class BatchDetectRequest(BaseModel):
    dataset_id: int
    split: str = "test"
    model_run_ids: list[int] = []
    ml_policy: str = "any"


class BatchDetectResponse(BaseModel):
    n_cases: int
    counts_by_label: dict[str, int]


class HybridDecisionResponse(BaseModel):
    decision_id: int
    case_pk: int
    case_id: str
    ml_policy: str
    final_label: str
    reason_code: str
    decided_at: datetime


class DecisionDetailResponse(BaseModel):
    case_pk: int
    case_id: str
    final_label: str
    reason_code: str
    fsm: dict[str, Any]
    ml: list[dict[str, Any]] = []
    explanations: list[dict[str, Any]] = []
