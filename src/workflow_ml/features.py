from collections import Counter
from collections.abc import Sequence
from datetime import datetime

import numpy as np

from src.common.types import Trace

FEATURE_SPEC_VERSION: str = "1.0.0"

CANONICAL_ALPHABET: tuple[str, ...] = (
    "OrderCreated",
    "PaymentInitiated",
    "PaymentAuthorized",
    "PaymentFailed",
    "OrderPacked",
    "OrderShipped",
    "OrderDelivered",
    "OrderCancelled",
    "RefundRequested",
    "RefundCompleted",
    "OrderClosed",
)


def get_feature_names() -> list[str]:
    """
    Returns the ordered list of exactly 145 feature names per Doc 05 §2.

    Categories:
    - Length (2): n_events, n_distinct_events
    - Event counts (11): count_<symbol> for all symbols in canonical alphabet
    - Bigram counts (121): bigram_<a>_<b> for all ordered pairs in alphabet x alphabet
    - Payment behaviour (3): payment_attempts, payment_failures, retry_ratio
    - Repetition (1): max_run_same_event
    - Timing (6): log1p_total_duration, log1p_mean_gap, log1p_max_gap,
                  log1p_min_gap, log1p_std_gap, max_gap_div_median_gap
    - Termination (1): ends_with_closed
    Total: 2 + 11 + 121 + 3 + 1 + 6 + 1 = 145 features.
    """
    names: list[str] = []

    # 1. Length (2)
    names.extend(["n_events", "n_distinct_events"])

    # 2. Event counts (11)
    for sym in CANONICAL_ALPHABET:
        names.append(f"count_{sym}")

    # 3. Bigram counts (121)
    for a in CANONICAL_ALPHABET:
        for b in CANONICAL_ALPHABET:
            names.append(f"bigram_{a}__{b}")

    # 4. Payment behaviour (3)
    names.extend(["payment_attempts", "payment_failures", "retry_ratio"])

    # 5. Repetition (1)
    names.append("max_run_same_event")

    # 6. Timing (6)
    names.extend(
        [
            "log1p_total_duration",
            "log1p_mean_gap",
            "log1p_max_gap",
            "log1p_min_gap",
            "log1p_std_gap",
            "max_gap_div_median_gap",
        ]
    )

    # 7. Termination (1)
    names.append("ends_with_closed")

    return names


def _extract_single_trace(trace: Trace, feature_names: list[str]) -> list[float]:
    events = trace.events
    activities = [e.activity for e in events]
    n_events = len(activities)

    # 1. Length
    feat_n_events = float(n_events)
    feat_n_distinct = float(len(set(activities)))

    # 2. Event counts
    cnt = Counter(activities)
    event_counts = [float(cnt[sym]) for sym in CANONICAL_ALPHABET]

    # 3. Bigram counts
    bigram_counts: list[float] = []
    if n_events >= 2:
        bigram_cnt = Counter(zip(activities[:-1], activities[1:]))
    else:
        bigram_cnt = Counter()

    for a in CANONICAL_ALPHABET:
        for b in CANONICAL_ALPHABET:
            bigram_counts.append(float(bigram_cnt[(a, b)]))

    # 4. Payment behaviour
    pi_cnt = float(cnt["PaymentInitiated"])
    pf_cnt = float(cnt["PaymentFailed"])
    retry_ratio = (pf_cnt / pi_cnt) if pi_cnt > 0.0 else 0.0
    payment_feats = [pi_cnt, pf_cnt, retry_ratio]

    # 5. Repetition (max_run_same_event)
    max_run = 0
    cur_run = 0
    prev_act = None
    for act in activities:
        if act == prev_act:
            cur_run += 1
        else:
            cur_run = 1
            prev_act = act
        if cur_run > max_run:
            max_run = cur_run
    feat_max_run = float(max_run)

    # 6. Timing
    if n_events <= 1:
        log1p_total_dur = 0.0
        log1p_mean_gap = 0.0
        log1p_max_gap = 0.0
        log1p_min_gap = 0.0
        log1p_std_gap = 0.0
        max_div_median = 1.0
    else:
        timestamps: list[datetime] = [e.timestamp for e in events]
        gaps = [
            max(0.0, (t2 - t1).total_seconds()) for t1, t2 in zip(timestamps[:-1], timestamps[1:])
        ]
        total_dur = max(0.0, (timestamps[-1] - timestamps[0]).total_seconds())

        mean_gap = float(np.mean(gaps))
        max_gap = float(np.max(gaps))
        min_gap = float(np.min(gaps))
        std_gap = float(np.std(gaps))
        median_gap = float(np.median(gaps))

        log1p_total_dur = float(np.log1p(total_dur))
        log1p_mean_gap = float(np.log1p(mean_gap))
        log1p_max_gap = float(np.log1p(max_gap))
        log1p_min_gap = float(np.log1p(min_gap))
        log1p_std_gap = float(np.log1p(std_gap))
        max_div_median = float(max_gap / (median_gap + 1e-6))

    timing_feats = [
        log1p_total_dur,
        log1p_mean_gap,
        log1p_max_gap,
        log1p_min_gap,
        log1p_std_gap,
        max_div_median,
    ]

    # 7. Termination
    ends_with_closed = 1.0 if (activities and activities[-1] == "OrderClosed") else 0.0

    # Combine in exact order
    row: list[float] = []
    row.append(feat_n_events)
    row.append(feat_n_distinct)
    row.extend(event_counts)
    row.extend(bigram_counts)
    row.extend(payment_feats)
    row.append(feat_max_run)
    row.extend(timing_feats)
    row.append(ends_with_closed)

    return row


def extract(traces: Sequence[Trace]) -> tuple[np.ndarray, list[str]]:
    """
    Extract 144-dimensional feature matrix and feature names from traces.

    All features are computed ONLY from event sequence and timestamps.
    Zero leakage: no DFA, labels, injector parameters, case IDs or split names.

    Args:
        traces: Sequence of Trace objects.

    Returns:
        tuple[np.ndarray, list[str]]: (matrix of shape (N, 144), list of 144 feature names)
    """
    feature_names = get_feature_names()
    if not traces:
        return np.empty((0, len(feature_names)), dtype=np.float64), feature_names

    rows = [_extract_single_trace(t, feature_names) for t in traces]
    matrix = np.asarray(rows, dtype=np.float64)
    return matrix, feature_names
