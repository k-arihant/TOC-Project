from datetime import datetime, timezone

import numpy as np

from src.common.interfaces import AnomalyDetector
from src.common.types import Event, Trace
from src.workflow_ml.random_forest import RandomForestDetector


def generate_traces(n: int, seed: int = 42) -> list[Trace]:
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
                    case_id=f"rf_{i}",
                    activity=act,
                    timestamp=datetime.fromtimestamp(cur_t, tz=timezone.utc),
                )
            )
        traces.append(Trace(case_id=f"rf_{i}", events=events))
    return traces


def test_random_forest_protocol_conformance():
    detector = RandomForestDetector()
    assert isinstance(detector, AnomalyDetector)
    assert detector.name == "random_forest"


def test_random_forest_supervised_fit_and_score():
    train_traces = generate_traces(20, seed=1)
    # half clean, half anomalous
    train_labels = [0] * 10 + [1] * 10
    val_traces = generate_traces(10, seed=2)
    test_traces = generate_traces(5, seed=3)

    detector = RandomForestDetector(n_estimators=30, random_state=42)
    detector.fit_supervised(train_traces, train_labels)
    detector.calibrate(val_traces, target_fpr=0.05)
    scores = detector.score(test_traces)

    assert len(scores) == 5
    for s in scores:
        assert 0.0 <= s.raw_score <= 1.0
        assert 0.0 <= s.norm_score <= 1.0
        assert len(s.factors) <= 3


def test_random_forest_serialization_round_trip():
    train_traces = generate_traces(10, seed=5)
    train_labels = [0] * 5 + [1] * 5
    val_traces = generate_traces(5, seed=6)
    test_traces = generate_traces(3, seed=7)

    detector = RandomForestDetector(n_estimators=20, random_state=42)
    detector.fit_supervised(train_traces, train_labels)
    detector.calibrate(val_traces, target_fpr=0.05)
    scores_before = detector.score(test_traces)

    blob = detector.to_bytes()
    restored = RandomForestDetector.from_bytes(blob)
    scores_after = restored.score(test_traces)

    for b, a in zip(scores_before, scores_after):
        assert b.case_id == a.case_id
        assert np.isclose(b.raw_score, a.raw_score)
        assert np.isclose(b.norm_score, a.norm_score)
        assert b.is_anomaly == a.is_anomaly
        assert len(b.factors) == len(a.factors)
