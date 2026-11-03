import pytest

from src.common.types import DetectorScore, Factor, FinalLabel, FsmResult, FsmVerdict
from src.hybrid.decision import DecisionPolicy, decide


def make_fsm_result(case_id: str, verdict: FsmVerdict) -> FsmResult:
    if verdict == FsmVerdict.VALID_COMPLETE:
        return FsmResult(
            case_id=case_id,
            verdict=verdict,
            state_path=["S0", "S1", "S12"],
        )
    if verdict == FsmVerdict.VALID_PREFIX:
        return FsmResult(
            case_id=case_id,
            verdict=verdict,
            state_path=["S0", "S1"],
            allowed_events=["PaymentInitiated", "OrderCancelled"],
        )
    # INVALID
    return FsmResult(
        case_id=case_id,
        verdict=verdict,
        state_path=["S0", "S1"],
        fail_index=1,
        fail_state="S1",
        fail_event="OrderShipped",
        allowed_events=["PaymentInitiated", "OrderCancelled"],
        reason_code="ILLEGAL_TRANSITION",
    )


def make_detector_score(case_id: str, detector: str, is_anomaly: bool) -> DetectorScore:
    return DetectorScore(
        case_id=case_id,
        detector=detector,
        raw_score=0.9 if is_anomaly else 0.1,
        norm_score=0.98 if is_anomaly else 0.40,
        threshold=0.95,
        is_anomaly=is_anomaly,
        factors=[Factor(name="feat", value=10.0, reference=2.0, note="high feature value")]
        if is_anomaly
        else [],
    )


def test_row_1_invalid_with_no_ml():
    """Row 1: INVALID + ML no -> RULE_VIOLATION"""
    fsm = make_fsm_result("c1", FsmVerdict.INVALID)
    scores = [make_detector_score("c1", "isolation_forest", False)]

    decision = decide(fsm, scores)
    assert decision.final_label == FinalLabel.RULE_VIOLATION
    assert decision.fsm.verdict == FsmVerdict.INVALID
    assert len(decision.explanation) >= 1


def test_row_1_invalid_with_ml_yes_cannot_override_fsm():
    """Row 1: INVALID + ML yes -> RULE_VIOLATION (formal rule violation is never overridden)"""
    fsm = make_fsm_result("c2", FsmVerdict.INVALID)
    scores = [make_detector_score("c2", "isolation_forest", True)]

    decision = decide(fsm, scores)
    assert decision.final_label == FinalLabel.RULE_VIOLATION
    assert any("Also statistically unusual" in line for line in decision.explanation)


def test_row_2_valid_complete_with_ml_yes():
    """Row 2: VALID_COMPLETE + ML yes -> STATISTICAL_ANOMALY"""
    fsm = make_fsm_result("c3", FsmVerdict.VALID_COMPLETE)
    scores = [make_detector_score("c3", "isolation_forest", True)]

    decision = decide(fsm, scores)
    assert decision.final_label == FinalLabel.STATISTICAL_ANOMALY
    assert any("valid under the workflow rules" in line for line in decision.explanation)
    assert any("isolation_forest" in line for line in decision.explanation)


def test_row_3_valid_complete_with_no_ml():
    """Row 3: VALID_COMPLETE + ML no -> NORMAL"""
    fsm = make_fsm_result("c4", FsmVerdict.VALID_COMPLETE)
    scores = [make_detector_score("c4", "isolation_forest", False)]

    decision = decide(fsm, scores)
    assert decision.final_label == FinalLabel.NORMAL
    assert any("No rule violation" in line for line in decision.explanation)


def test_row_4_valid_prefix_incomplete_trace():
    """Row 4: VALID_PREFIX + any ML -> IN_PROGRESS (ML not applied to incomplete traces)"""
    fsm = make_fsm_result("c5", FsmVerdict.VALID_PREFIX)
    # Even if ML flagged an anomaly on prefix, final label remains IN_PROGRESS
    scores = [make_detector_score("c5", "isolation_forest", True)]

    decision = decide(fsm, scores)
    assert decision.final_label == FinalLabel.IN_PROGRESS
    assert any(
        "ML anomaly detection is not applied to incomplete traces" in line
        for line in decision.explanation
    )


def test_decision_policy_any():
    policy = DecisionPolicy("any")
    s_clean = make_detector_score("c", "if", False)
    s_ano = make_detector_score("c", "mk", True)

    assert policy.apply([s_clean, s_clean]) is False
    assert policy.apply([s_clean, s_ano]) is True
    assert policy.apply([]) is False


def test_decision_policy_all():
    policy = DecisionPolicy("all")
    s_clean = make_detector_score("c", "if", False)
    s_ano1 = make_detector_score("c", "if", True)
    s_ano2 = make_detector_score("c", "mk", True)

    assert policy.apply([s_clean, s_ano2]) is False
    assert policy.apply([s_ano1, s_ano2]) is True
    assert policy.apply([]) is False


def test_decision_policy_primary():
    policy = DecisionPolicy("primary:markov")
    s_if_ano = make_detector_score("c", "isolation_forest", True)
    s_mk_clean = make_detector_score("c", "markov", False)
    s_mk_ano = make_detector_score("c", "markov", True)

    # Markov is clean -> policy returns False even though IF flagged anomaly
    assert policy.apply([s_if_ano, s_mk_clean]) is False

    # Markov is anomalous -> policy returns True
    assert policy.apply([s_if_ano, s_mk_ano]) is True


def test_invalid_policy_raises():
    with pytest.raises(ValueError, match="Unknown decision policy"):
        DecisionPolicy("unknown_policy_format")
