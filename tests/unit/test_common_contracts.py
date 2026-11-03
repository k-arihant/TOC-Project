"""Tests for shared contracts in src.common."""
from datetime import datetime, timezone
from typing import Sequence

from src.common.config import settings
from src.common.interfaces import AnomalyDetector
from src.common.types import (
    DetectorScore,
    Event,
    Factor,
    FinalLabel,
    FsmResult,
    FsmVerdict,
    HybridDecision,
    Trace,
)


def test_event_and_trace_contracts():
    now = datetime.now(timezone.utc)
    event1 = Event(case_id="c1", activity="OrderCreated", timestamp=now)
    event2 = Event(case_id="c1", activity="PaymentInitiated", timestamp=now)

    trace = Trace(case_id="c1", events=[event1, event2])
    assert trace.case_id == "c1"
    assert trace.activities == ["OrderCreated", "PaymentInitiated"]
    assert len(trace.events) == 2


def test_fsm_result_contract():
    result = FsmResult(
        case_id="c1",
        verdict=FsmVerdict.INVALID,
        state_path=["Start", "Created"],
        fail_index=1,
        fail_state="Created",
        fail_event="OrderShipped",
        allowed_events=["PaymentInitiated", "OrderCancelled"],
        reason_code="ILLEGAL_TRANSITION",
    )
    assert result.verdict == FsmVerdict.INVALID
    assert result.fail_index == 1
    assert result.reason_code == "ILLEGAL_TRANSITION"


def test_detector_score_contract():
    factor = Factor(name="gap", value=500.0, reference=60.0, note="Unusually long gap")
    score = DetectorScore(
        case_id="c1",
        detector="isolation_forest",
        raw_score=0.85,
        norm_score=0.92,
        threshold=0.80,
        is_anomaly=True,
        factors=[factor],
    )
    assert score.raw_score == 0.85
    assert score.norm_score == 0.92
    assert score.is_anomaly is True
    assert len(score.factors) == 1


def test_hybrid_decision_contract():
    fsm = FsmResult(case_id="c1", verdict=FsmVerdict.VALID_COMPLETE, state_path=["Start", "Closed"])
    decision = HybridDecision(
        case_id="c1",
        final_label=FinalLabel.NORMAL,
        fsm=fsm,
        ml=[],
        explanation=["Normal execution trace."],
    )
    assert decision.final_label == FinalLabel.NORMAL
    assert decision.fsm.verdict == FsmVerdict.VALID_COMPLETE
    assert len(decision.explanation) == 1


def test_anomaly_detector_protocol():
    class DummyDetector:
        name = "dummy"

        def fit(self, traces: Sequence[Trace]) -> None:
            pass

        def calibrate(self, traces: Sequence[Trace], target_fpr: float) -> None:
            pass

        def score(self, traces: Sequence[Trace]) -> list[DetectorScore]:
            return []

        def to_bytes(self) -> bytes:
            return b"dummy"

        @classmethod
        def from_bytes(cls, b: bytes) -> "DummyDetector":
            return cls()

    detector: AnomalyDetector = DummyDetector()
    assert detector.name == "dummy"
    assert detector.to_bytes() == b"dummy"


def test_config_settings():
    assert settings.API_PORT == 8000
    assert settings.LOG_LEVEL == "INFO"
    assert "http://localhost:8501" in settings.cors_origins_list
