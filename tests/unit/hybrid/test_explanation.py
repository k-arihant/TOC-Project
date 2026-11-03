from src.common.types import DetectorScore, Factor, FinalLabel, FsmResult, FsmVerdict
from src.hybrid.decision import decide
from src.hybrid.explanation import explain_hybrid, explain_ml


def make_fsm_result(verdict: FsmVerdict) -> FsmResult:
    if verdict == FsmVerdict.VALID_COMPLETE:
        return FsmResult(
            case_id="case_vc",
            verdict=verdict,
            state_path=["S0", "S1", "S12"],
        )
    if verdict == FsmVerdict.VALID_PREFIX:
        return FsmResult(
            case_id="case_vp",
            verdict=verdict,
            state_path=["S0", "S1"],
            allowed_events=["PaymentInitiated", "OrderCancelled"],
        )
    return FsmResult(
        case_id="case_inv",
        verdict=verdict,
        state_path=["S0", "S1"],
        fail_index=1,
        fail_state="S1",
        fail_event="OrderShipped",
        allowed_events=["PaymentInitiated", "OrderCancelled"],
        reason_code="ILLEGAL_TRANSITION",
    )


def test_explanation_completeness_all_labels():
    """
    Mandatory completeness test per Doc 11 §3 Phase 5:
    Confirms >= 1 explanation sentence for every case across all 4 labels.
    """
    cases = [
        (FsmVerdict.INVALID, [DetectorScore("c", "if", 0.9, 0.98, 0.95, True)]),
        (FsmVerdict.INVALID, [DetectorScore("c", "if", 0.1, 0.20, 0.95, False)]),
        (FsmVerdict.VALID_COMPLETE, [DetectorScore("c", "if", 0.9, 0.98, 0.95, True)]),
        (FsmVerdict.VALID_COMPLETE, [DetectorScore("c", "if", 0.1, 0.20, 0.95, False)]),
        (FsmVerdict.VALID_PREFIX, [DetectorScore("c", "if", 0.9, 0.98, 0.95, True)]),
        (FsmVerdict.VALID_PREFIX, [DetectorScore("c", "if", 0.1, 0.20, 0.95, False)]),
    ]

    for verdict, scores in cases:
        fsm = make_fsm_result(verdict)
        decision = decide(fsm, scores)
        assert len(decision.explanation) >= 1
        for line in decision.explanation:
            assert isinstance(line, str)
            assert len(line.strip()) > 0


def test_explain_ml_formatting():
    score = DetectorScore(
        case_id="case_1",
        detector="isolation_forest",
        raw_score=0.85,
        norm_score=0.97,
        threshold=0.95,
        is_anomaly=True,
        factors=[
            Factor(
                name="payment_attempts",
                value=5.0,
                reference=1.0,
                note="payment_attempts=5 (training median=1)",
            ),
            Factor(name="log1p_mean_gap", value=0.1, reference=2.5, note="unusually fast timing"),
        ],
    )
    lines = explain_ml(score)
    assert len(lines) == 3
    assert "isolation_forest" in lines[0]
    assert "0.9700" in lines[0]
    assert "payment_attempts=5" in lines[1]
    assert "unusually fast timing" in lines[2]


def test_explain_hybrid_state_names_mapping():
    fsm = make_fsm_result(FsmVerdict.INVALID)
    state_names = {"S0": "Start", "S1": "Created"}
    lines = explain_hybrid(
        fsm=fsm,
        scores=[],
        final_label=FinalLabel.RULE_VIOLATION,
        ml_flag=False,
        state_names=state_names,
    )
    assert any("S1 (Created)" in line for line in lines)
