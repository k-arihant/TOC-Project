from datetime import datetime, timezone

import pytest

from src.automata.loader import load_workflow
from src.common.types import DetectorScore, Event, FinalLabel, FsmResult, FsmVerdict, Trace
from src.hybrid.pipeline import decide_batch, run_hybrid_pipeline
from src.research.markov import MarkovDetector
from src.workflow_ml.isolation_forest import IsolationForestDetector


def make_trace(case_id: str, activities: list[str], gap_seconds: float = 10.0) -> Trace:
    events = []
    base_ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    for i, act in enumerate(activities):
        ts = datetime.fromtimestamp(base_ts.timestamp() + i * gap_seconds, tz=timezone.utc)
        events.append(
            Event(
                case_id=case_id,
                activity=act,
                timestamp=ts,
            )
        )
    return Trace(case_id=case_id, events=events)


def test_decide_batch_ordering_and_mapping():
    t1 = make_trace("c1", ["OrderCreated", "OrderClosed"])
    t2 = make_trace("c2", ["OrderCreated"])

    fsm1 = FsmResult(
        case_id="c1", verdict=FsmVerdict.VALID_COMPLETE, state_path=["S0", "S1", "S12"]
    )
    fsm2 = FsmResult(case_id="c2", verdict=FsmVerdict.VALID_PREFIX, state_path=["S0", "S1"])

    scores_by_det = {
        "isolation_forest": [
            DetectorScore("c1", "isolation_forest", 0.1, 0.2, 0.95, False),
            DetectorScore("c2", "isolation_forest", 0.1, 0.2, 0.95, False),
        ]
    }

    decisions = decide_batch([t1, t2], [fsm1, fsm2], scores_by_det)
    assert len(decisions) == 2
    assert decisions[0].case_id == "c1"
    assert decisions[0].final_label == FinalLabel.NORMAL
    assert decisions[1].case_id == "c2"
    assert decisions[1].final_label == FinalLabel.IN_PROGRESS


def test_decide_batch_missing_fsm_raises():
    t1 = make_trace("c1", ["OrderCreated"])
    with pytest.raises(KeyError, match="Missing FsmResult for case 'c1'"):
        decide_batch([t1], [], {})


def test_run_hybrid_pipeline_end_to_end():
    dfa = load_workflow("workflows/order_payment/workflow.yaml")

    # Diverse valid paths (normal execution, 1 retry, early cancellation)
    p_happy = [
        "OrderCreated",
        "PaymentInitiated",
        "PaymentAuthorized",
        "OrderPacked",
        "OrderShipped",
        "OrderDelivered",
        "OrderClosed",
    ]
    p_retry = [
        "OrderCreated",
        "PaymentInitiated",
        "PaymentFailed",
        "PaymentInitiated",
        "PaymentAuthorized",
        "OrderPacked",
        "OrderShipped",
        "OrderDelivered",
        "OrderClosed",
    ]
    p_cancel = [
        "OrderCreated",
        "PaymentInitiated",
        "OrderCancelled",
    ]
    valid_paths = [p_happy, p_retry, p_cancel]

    train_normal = [
        make_trace(
            f"train_{i}",
            valid_paths[i % len(valid_paths)],
            gap_seconds=10.0 + (i % 7) * 3.0,
        )
        for i in range(45)
    ]

    val_normal = [
        make_trace(
            f"val_{i}",
            valid_paths[i % len(valid_paths)],
            gap_seconds=11.0 + (i % 5) * 2.5,
        )
        for i in range(21)
    ]

    if_det = IsolationForestDetector(n_estimators=50, random_state=42)
    if_det.fit(train_normal)
    if_det.calibrate(val_normal, target_fpr=0.05)

    mk_det = MarkovDetector(alpha=1.0)
    mk_det.fit(train_normal)
    mk_det.calibrate(val_normal, target_fpr=0.05)

    # Test traces:
    # 1. Normal complete trace with typical timing
    t_normal = make_trace(
        "test_norm",
        p_happy,
        gap_seconds=12.0,
    )
    # 2. Rule violation trace: illegal transition OrderCreated -> OrderShipped
    t_rule_viol = make_trace(
        "test_viol",
        ["OrderCreated", "OrderShipped"],
        gap_seconds=10.0,
    )
    # 3. Incomplete trace (prefix)
    t_prefix = make_trace(
        "test_pref",
        ["OrderCreated", "PaymentInitiated"],
        gap_seconds=10.0,
    )

    decisions = run_hybrid_pipeline(
        traces=[t_normal, t_rule_viol, t_prefix],
        dfa=dfa,
        detectors=[if_det, mk_det],
        policy="any",
    )

    assert len(decisions) == 3

    # Normal trace evaluation
    assert decisions[0].case_id == "test_norm"
    assert decisions[0].final_label == FinalLabel.NORMAL
    assert decisions[0].fsm.verdict == FsmVerdict.VALID_COMPLETE

    # Rule violation trace evaluation
    assert decisions[1].case_id == "test_viol"
    assert decisions[1].final_label == FinalLabel.RULE_VIOLATION
    assert decisions[1].fsm.verdict == FsmVerdict.INVALID

    # Prefix trace evaluation
    assert decisions[2].case_id == "test_pref"
    assert decisions[2].final_label == FinalLabel.IN_PROGRESS
    assert decisions[2].fsm.verdict == FsmVerdict.VALID_PREFIX
