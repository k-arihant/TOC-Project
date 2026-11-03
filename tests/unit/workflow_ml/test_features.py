from datetime import datetime, timezone

import numpy as np

from src.common.types import Event, Trace
from src.workflow_ml.features import extract, get_feature_names


def make_test_trace(case_id: str, activities: list[str], gap_seconds: float = 10.0) -> Trace:
    events = []
    base_ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    for i, act in enumerate(activities):
        ts = datetime.fromtimestamp(base_ts.timestamp() + i * gap_seconds, tz=timezone.utc)
        events.append(Event(case_id=case_id, activity=act, timestamp=ts))
    return Trace(case_id=case_id, events=events)


def test_feature_names_count():
    names = get_feature_names()
    assert len(names) == 145
    assert len(set(names)) == 145  # Unique names


def test_feature_extraction_empty_traces():
    matrix, names = extract([])
    assert len(names) == 145
    assert matrix.shape == (0, 145)


def test_feature_extraction_single_event():
    trace = make_test_trace("case_single", ["OrderCreated"], gap_seconds=0.0)
    matrix, names = extract([trace])

    assert matrix.shape == (1, 145)
    # n_events = 1, n_distinct = 1
    assert matrix[0, names.index("n_events")] == 1.0
    assert matrix[0, names.index("n_distinct_events")] == 1.0
    assert matrix[0, names.index("count_OrderCreated")] == 1.0
    assert matrix[0, names.index("count_OrderClosed")] == 0.0
    assert matrix[0, names.index("ends_with_closed")] == 0.0
    assert matrix[0, names.index("max_run_same_event")] == 1.0


def test_feature_extraction_normal_complete_trace():
    acts = [
        "OrderCreated",
        "PaymentInitiated",
        "PaymentAuthorized",
        "OrderPacked",
        "OrderShipped",
        "OrderDelivered",
        "OrderClosed",
    ]
    trace = make_test_trace("case_norm", acts, gap_seconds=10.0)
    matrix, names = extract([trace])

    assert matrix.shape == (1, 145)
    assert matrix[0, names.index("n_events")] == 7.0
    assert matrix[0, names.index("n_distinct_events")] == 7.0
    assert matrix[0, names.index("count_OrderCreated")] == 1.0
    assert matrix[0, names.index("count_PaymentInitiated")] == 1.0
    assert matrix[0, names.index("payment_attempts")] == 1.0
    assert matrix[0, names.index("payment_failures")] == 0.0
    assert matrix[0, names.index("retry_ratio")] == 0.0
    assert matrix[0, names.index("ends_with_closed")] == 1.0

    # Bigram checks
    assert matrix[0, names.index("bigram_OrderCreated__PaymentInitiated")] == 1.0
    assert matrix[0, names.index("bigram_PaymentInitiated__PaymentAuthorized")] == 1.0
    assert matrix[0, names.index("bigram_PaymentInitiated__PaymentFailed")] == 0.0

    # Timing checks: 6 gaps of 10.0s, total = 60.0s
    total_dur_idx = names.index("log1p_total_duration")
    mean_gap_idx = names.index("log1p_mean_gap")
    assert np.isclose(matrix[0, total_dur_idx], np.log1p(60.0))
    assert np.isclose(matrix[0, mean_gap_idx], np.log1p(10.0))


def test_feature_extraction_payment_retries():
    acts = [
        "OrderCreated",
        "PaymentInitiated",
        "PaymentFailed",
        "PaymentInitiated",
        "PaymentFailed",
        "PaymentInitiated",
        "PaymentAuthorized",
        "OrderPacked",
        "OrderShipped",
        "OrderDelivered",
        "OrderClosed",
    ]
    trace = make_test_trace("case_retry", acts, gap_seconds=5.0)
    matrix, names = extract([trace])

    assert matrix[0, names.index("payment_attempts")] == 3.0
    assert matrix[0, names.index("payment_failures")] == 2.0
    assert np.isclose(matrix[0, names.index("retry_ratio")], 2.0 / 3.0)
    assert matrix[0, names.index("bigram_PaymentInitiated__PaymentFailed")] == 2.0
    assert matrix[0, names.index("bigram_PaymentFailed__PaymentInitiated")] == 2.0


def test_repetition_feature():
    acts = [
        "OrderCreated",
        "PaymentInitiated",
        "PaymentInitiated",
        "PaymentInitiated",
        "OrderCancelled",
    ]
    trace = make_test_trace("case_rep", acts, gap_seconds=2.0)
    matrix, names = extract([trace])

    assert matrix[0, names.index("max_run_same_event")] == 3.0
