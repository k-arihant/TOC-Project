from datetime import datetime, timezone

import numpy as np

from src.common.interfaces import AnomalyDetector
from src.common.types import Event, Trace
from src.research.markov import MarkovDetector


def make_trace(case_id: str, acts: list[str]) -> Trace:
    events = [
        Event(
            case_id=case_id,
            activity=act,
            timestamp=datetime(2026, 1, 1, 12, i, 0, tzinfo=timezone.utc),
        )
        for i, act in enumerate(acts)
    ]
    return Trace(case_id=case_id, events=events)


def test_markov_protocol_conformance():
    detector = MarkovDetector()
    assert isinstance(detector, AnomalyDetector)
    assert detector.name == "markov"


def test_markov_row_probabilities_sum_to_one():
    traces = [
        make_trace("c1", ["OrderCreated", "PaymentInitiated", "PaymentAuthorized", "OrderClosed"]),
        make_trace("c2", ["OrderCreated", "PaymentInitiated", "PaymentFailed", "OrderCancelled"]),
    ]

    detector = MarkovDetector(alpha=1.0)
    detector.fit(traces)

    for u, trans_map in detector.transition_probs.items():
        total_p = sum(trans_map.values())
        assert np.isclose(total_p, 1.0), f"Row sum for state {u} was {total_p}, expected 1.0"


def test_markov_laplace_smoothing_nonzero():
    traces = [
        make_trace("c1", ["OrderCreated", "OrderClosed"]),
    ]
    detector = MarkovDetector(alpha=1.0)
    detector.fit(traces)

    # An unseen transition: OrderCreated -> PaymentFailed
    unseen_prob = detector._transition_prob("OrderCreated", "PaymentFailed")
    assert unseen_prob > 0.0


def test_markov_scoring_modes():
    train_traces = [
        make_trace("c1", ["OrderCreated", "PaymentInitiated", "PaymentAuthorized", "OrderClosed"]),
        make_trace("c2", ["OrderCreated", "PaymentInitiated", "PaymentAuthorized", "OrderClosed"]),
    ]
    test_traces = [
        make_trace("test1", ["OrderCreated", "OrderClosed"]),
    ]

    # Mean NLL
    det_mean = MarkovDetector(scoring_mode="mean_nll")
    det_mean.fit(train_traces)
    det_mean.calibrate(train_traces, target_fpr=0.05)
    scores_mean = det_mean.score(test_traces)

    # Total NLL
    det_total = MarkovDetector(scoring_mode="total_nll")
    det_total.fit(train_traces)
    det_total.calibrate(train_traces, target_fpr=0.05)
    scores_total = det_total.score(test_traces)

    assert len(scores_mean) == 1
    assert len(scores_total) == 1
    assert 0.0 <= scores_mean[0].norm_score <= 1.0
    assert 0.0 <= scores_total[0].norm_score <= 1.0
    assert len(scores_mean[0].factors) <= 3


def test_markov_serialization_round_trip():
    train_traces = [
        make_trace("c1", ["OrderCreated", "PaymentInitiated", "PaymentAuthorized", "OrderClosed"]),
    ]
    test_traces = [
        make_trace("test1", ["OrderCreated", "PaymentFailed", "OrderCancelled"]),
    ]

    detector = MarkovDetector(alpha=1.0, scoring_mode="mean_nll")
    detector.fit(train_traces)
    detector.calibrate(train_traces, target_fpr=0.05)
    scores_before = detector.score(test_traces)

    blob = detector.to_bytes()
    restored = MarkovDetector.from_bytes(blob)
    scores_after = restored.score(test_traces)

    assert np.isclose(scores_before[0].raw_score, scores_after[0].raw_score)
    assert np.isclose(scores_before[0].norm_score, scores_after[0].norm_score)
    assert scores_before[0].is_anomaly == scores_after[0].is_anomaly
    assert len(scores_before[0].factors) == len(scores_after[0].factors)
