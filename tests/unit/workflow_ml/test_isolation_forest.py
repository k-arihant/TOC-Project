from datetime import datetime, timezone

import numpy as np

from src.common.interfaces import AnomalyDetector
from src.common.types import Event, Trace
from src.workflow_ml.isolation_forest import IsolationForestDetector


def generate_synthetic_traces(n: int, seed: int = 42) -> list[Trace]:
    rng = np.random.default_rng(seed)
    traces = []
    base_ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    for i in range(n):
        acts = [
            "OrderCreated",
            "PaymentInitiated",
            "PaymentAuthorized",
            "OrderPacked",
            "OrderShipped",
            "OrderDelivered",
            "OrderClosed",
        ]
        events = []
        cur_t = base_ts.timestamp() + i * 3600
        for act in acts:
            cur_t += rng.uniform(5.0, 30.0)
            events.append(
                Event(
                    case_id=f"c_{i}",
                    activity=act,
                    timestamp=datetime.fromtimestamp(cur_t, tz=timezone.utc),
                )
            )
        traces.append(Trace(case_id=f"c_{i}", events=events))
    return traces


def test_isolation_forest_protocol_conformance():
    detector = IsolationForestDetector()
    assert isinstance(detector, AnomalyDetector)
    assert detector.name == "isolation_forest"


def test_isolation_forest_end_to_end_and_determinism():
    train_traces = generate_synthetic_traces(30, seed=1)
    val_traces = generate_synthetic_traces(10, seed=2)
    test_traces = generate_synthetic_traces(5, seed=3)

    # First run
    det1 = IsolationForestDetector(n_estimators=50, random_state=42)
    det1.fit(train_traces)
    det1.calibrate(val_traces, target_fpr=0.05)
    scores1 = det1.score(test_traces)

    # Second run with same seed
    det2 = IsolationForestDetector(n_estimators=50, random_state=42)
    det2.fit(train_traces)
    det2.calibrate(val_traces, target_fpr=0.05)
    scores2 = det2.score(test_traces)

    assert len(scores1) == 5
    for s1, s2 in zip(scores1, scores2):
        assert s1.case_id == s2.case_id
        assert np.isclose(s1.raw_score, s2.raw_score)
        assert np.isclose(s1.norm_score, s2.norm_score)
        assert s1.is_anomaly == s2.is_anomaly
        assert 0.0 <= s1.norm_score <= 1.0
        assert len(s1.factors) <= 3


def test_isolation_forest_serialization_round_trip():
    train_traces = generate_synthetic_traces(20, seed=10)
    val_traces = generate_synthetic_traces(10, seed=11)
    test_traces = generate_synthetic_traces(5, seed=12)

    detector = IsolationForestDetector(n_estimators=30, random_state=42)
    detector.fit(train_traces)
    detector.calibrate(val_traces, target_fpr=0.05)
    scores_before = detector.score(test_traces)

    # Serialize and deserialize
    blob = detector.to_bytes()
    restored = IsolationForestDetector.from_bytes(blob)
    scores_after = restored.score(test_traces)

    assert len(scores_before) == len(scores_after)
    for b, a in zip(scores_before, scores_after):
        assert b.case_id == a.case_id
        assert np.isclose(b.raw_score, a.raw_score)
        assert np.isclose(b.norm_score, a.norm_score)
        assert np.isclose(b.threshold, a.threshold)
        assert b.is_anomaly == a.is_anomaly
        assert len(b.factors) == len(a.factors)
