from datetime import datetime, timezone

import numpy as np

from src.common.interfaces import AnomalyDetector
from src.common.types import Event, Trace
from src.research.kmeans_score import KMeansDetector


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
                    case_id=f"k_{i}",
                    activity=act,
                    timestamp=datetime.fromtimestamp(cur_t, tz=timezone.utc),
                )
            )
        traces.append(Trace(case_id=f"k_{i}", events=events))
    return traces


def test_kmeans_protocol_conformance():
    detector = KMeansDetector()
    assert isinstance(detector, AnomalyDetector)
    assert detector.name == "kmeans"


def test_kmeans_end_to_end_and_determinism():
    train_traces = generate_traces(25, seed=1)
    val_traces = generate_traces(10, seed=2)
    test_traces = generate_traces(5, seed=3)

    det1 = KMeansDetector(n_clusters=3, random_state=42)
    det1.fit(train_traces)
    det1.calibrate(val_traces, target_fpr=0.05)
    scores1 = det1.score(test_traces)

    det2 = KMeansDetector(n_clusters=3, random_state=42)
    det2.fit(train_traces)
    det2.calibrate(val_traces, target_fpr=0.05)
    scores2 = det2.score(test_traces)

    assert len(scores1) == 5
    for s1, s2 in zip(scores1, scores2):
        assert s1.case_id == s2.case_id
        assert np.isclose(s1.raw_score, s2.raw_score)
        assert np.isclose(s1.norm_score, s2.norm_score)
        assert s1.raw_score >= 0.0
        assert 0.0 <= s1.norm_score <= 1.0
        assert len(s1.factors) <= 3


def test_kmeans_serialization_round_trip():
    train_traces = generate_traces(15, seed=5)
    val_traces = generate_traces(5, seed=6)
    test_traces = generate_traces(3, seed=7)

    detector = KMeansDetector(n_clusters=2, random_state=42)
    detector.fit(train_traces)
    detector.calibrate(val_traces, target_fpr=0.05)
    scores_before = detector.score(test_traces)

    blob = detector.to_bytes()
    restored = KMeansDetector.from_bytes(blob)
    scores_after = restored.score(test_traces)

    for b, a in zip(scores_before, scores_after):
        assert b.case_id == a.case_id
        assert np.isclose(b.raw_score, a.raw_score)
        assert np.isclose(b.norm_score, a.norm_score)
        assert b.is_anomaly == a.is_anomaly
        assert len(b.factors) == len(a.factors)
