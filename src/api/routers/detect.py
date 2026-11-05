"""Hybrid anomaly detection router."""

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.api.routers.automata import _dfa_from_model
from src.api.routers.ml import load_detector_from_model_run
from src.api.schemas.common import PaginatedResponse, PaginationMeta
from src.api.schemas.detect import (
    AnalyzeTraceRequest,
    AnalyzeTraceResponse,
    BatchDetectRequest,
    BatchDetectResponse,
    DecisionDetailResponse,
    FactorSchema,
    HybridDecisionResponse,
    MlScoreSchema,
)
from src.automata.loader import load_workflow
from src.automata.validator import validate_trace
from src.common.types import Event, Trace
from src.db.repositories.dataset_repo import DatasetRepository
from src.db.repositories.hybrid_repo import HybridRepository
from src.db.repositories.model_repo import ModelRepository
from src.db.repositories.workflow_repo import WorkflowRepository
from src.db.session import get_db
from src.hybrid.decision import decide

router = APIRouter(prefix="/detect", tags=["Hybrid Detection"])


@router.post("/analyze", response_model=AnalyzeTraceResponse)
def analyze_single_trace(
    payload: AnalyzeTraceRequest,
    db: Session = Depends(get_db),
) -> AnalyzeTraceResponse:
    """Analyze a single ad-hoc activity trace through formal FSM + ML hybrid fusion."""
    wf_repo = WorkflowRepository(db)
    auto = wf_repo.get_automaton_by_kind(payload.workflow_id, "DFA")
    dfa = _dfa_from_model(auto) if auto else load_workflow("workflows/order_payment/workflow.yaml")

    # 1. Formal FSM validation
    fsm_res = validate_trace(dfa=dfa, case_id=payload.case_id, activities=payload.activities)

    # 2. Score with ML detectors if provided
    m_repo = ModelRepository(db)
    trace = Trace(
        case_id=payload.case_id,
        events=[
            Event(case_id=payload.case_id, activity=act, timestamp=datetime.now(timezone.utc))
            for act in payload.activities
        ],
    )

    scores = []
    for mid in payload.model_run_ids:
        run = m_repo.get_model_run(mid)
        if run:
            detector = load_detector_from_model_run(run)
            res = detector.score([trace])
            if res:
                scores.append(res[0])

    # 3. Hybrid decision fusion
    hybrid_res = decide(fsm=fsm_res, scores=scores, policy=payload.ml_policy)

    fsm_dict: dict[str, Any] = {
        "verdict": fsm_res.verdict.value,
        "reason_code": fsm_res.reason_code,
        "fail_index": fsm_res.fail_index,
        "fail_state": fsm_res.fail_state,
        "fail_event": fsm_res.fail_event,
        "allowed_events": fsm_res.allowed_events or [],
        "state_path": fsm_res.state_path,
    }

    ml_schemas = [
        MlScoreSchema(
            detector=s.detector,
            raw_score=s.raw_score,
            norm_score=s.norm_score,
            threshold=s.threshold,
            is_anomaly=s.is_anomaly,
            factors=[
                FactorSchema(name=f.name, value=f.value, reference=f.reference, note=f.note)
                for f in s.factors
            ],
        )
        for s in scores
    ]

    return AnalyzeTraceResponse(
        case_id=payload.case_id,
        final_label=hybrid_res.final_label.value,
        fsm=fsm_dict,
        ml=ml_schemas,
        explanations=hybrid_res.explanation,
    )


@router.post("/batch", response_model=BatchDetectResponse)
def batch_detect(
    payload: BatchDetectRequest,
    db: Session = Depends(get_db),
) -> BatchDetectResponse:
    """Run batch hybrid anomaly detection over a dataset split and persist decisions."""
    ds_repo = DatasetRepository(db)
    wf_repo = WorkflowRepository(db)
    m_repo = ModelRepository(db)
    h_repo = HybridRepository(db)

    ds = ds_repo.get_dataset(payload.dataset_id)
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "DATASET_NOT_FOUND", "message": f"Dataset {payload.dataset_id} not found"},
        )

    traces = ds_repo.get_traces_for_dataset(payload.dataset_id, split=payload.split)
    if not traces:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "NO_TRACES_FOUND", "message": f"No traces found for split '{payload.split}'"},
        )

    auto = wf_repo.get_automaton_by_kind(ds.workflow_id, "DFA")
    dfa = _dfa_from_model(auto) if auto else load_workflow("workflows/order_payment/workflow.yaml")

    detectors = []
    for mid in payload.model_run_ids:
        run = m_repo.get_model_run(mid)
        if run:
            detectors.append((run, load_detector_from_model_run(run)))

    counts = {
        "NORMAL": 0,
        "RULE_VIOLATION": 0,
        "STATISTICAL_ANOMALY": 0,
        "IN_PROGRESS": 0,
    }

    automaton_id = auto.automaton_id if auto else 1

    for tr in traces:
        case_obj = ds_repo.get_case(payload.dataset_id, tr.case_id)
        if not case_obj:
            continue

        fsm_res = validate_trace(dfa=dfa, case_id=tr.case_id, activities=tr.activities)
        fsm_model = h_repo.record_fsm_result(case_obj.case_pk, automaton_id, fsm_res)

        pred_ids = []
        scores = []
        for run, det in detectors:
            score = det.score([tr])[0]
            scores.append(score)
            pred = m_repo.record_prediction(case_obj.case_pk, run.model_run_id, score)
            pred_ids.append(pred.prediction_id)

        decision = decide(fsm=fsm_res, scores=scores, policy=payload.ml_policy)
        h_repo.record_decision(
            case_pk=case_obj.case_pk,
            fsm_result_id=fsm_model.fsm_result_id,
            decision=decision,
            ml_policy=payload.ml_policy,
            prediction_ids=pred_ids,
        )
        counts[decision.final_label.value] = counts.get(decision.final_label.value, 0) + 1

    return BatchDetectResponse(
        n_cases=len(traces),
        counts_by_label=counts,
    )


@router.get("/results", response_model=PaginatedResponse[HybridDecisionResponse])
def get_detection_results(
    dataset_id: Optional[int] = Query(None),
    final_label: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> PaginatedResponse[HybridDecisionResponse]:
    """Retrieve paginated hybrid decisions with optional filters."""
    h_repo = HybridRepository(db)
    items, total = h_repo.list_decisions(
        dataset_id=dataset_id,
        final_label=final_label,
        page=page,
        page_size=page_size,
    )

    results = [
        HybridDecisionResponse(
            decision_id=d.decision_id,
            case_pk=d.case_pk,
            case_id=d.case.case_id if d.case else f"CASE-{d.case_pk}",
            ml_policy=d.ml_policy,
            final_label=d.final_label,
            reason_code=d.reason_code,
            decided_at=d.decided_at,
        )
        for d in items
    ]

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    return PaginatedResponse(
        items=results,
        pagination=PaginationMeta(
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=total_pages,
        ),
    )


@router.get("/results/{case_pk}", response_model=DecisionDetailResponse)
def get_case_decision_detail(
    case_pk: int,
    db: Session = Depends(get_db),
) -> DecisionDetailResponse:
    """Retrieve full decision details for a specific case."""
    h_repo = HybridRepository(db)
    dec = h_repo.get_decision_by_case(case_pk)
    if not dec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "DECISION_NOT_FOUND", "message": f"No hybrid decision found for case_pk {case_pk}"},
        )

    fsm_info: dict[str, Any] = {}
    if dec.fsm_result:
        f = dec.fsm_result
        fsm_info = {
            "verdict": f.verdict,
            "reason_code": f.reason_code,
            "fail_index": f.fail_index,
            "fail_state": f.fail_state,
            "fail_event": f.fail_event,
            "allowed_events": f.allowed_events,
            "state_path": f.state_path,
        }

    ml_info = []
    if dec.case and dec.case.ml_predictions:
        for p in dec.case.ml_predictions:
            ml_info.append(
                {
                    "detector": p.model_run.detector if p.model_run else "unknown",
                    "raw_score": p.raw_score,
                    "norm_score": p.norm_score,
                    "is_anomaly": p.is_anomaly,
                    "factors": p.factors,
                }
            )

    exp_info = [
        {"source": e.source, "rank": e.rank, "text": e.text}
        for e in sorted(dec.explanations, key=lambda x: x.rank)
    ]

    return DecisionDetailResponse(
        case_pk=dec.case_pk,
        case_id=dec.case.case_id if dec.case else str(dec.case_pk),
        final_label=dec.final_label,
        reason_code=dec.reason_code,
        fsm=fsm_info,
        ml=ml_info,
        explanations=exp_info,
    )
