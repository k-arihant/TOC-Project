from collections import defaultdict
from collections.abc import Sequence

from src.automata.dfa import DFA
from src.automata.validator import validate_trace
from src.common.interfaces import AnomalyDetector
from src.common.types import DetectorScore, FsmResult, HybridDecision, Trace
from src.hybrid.decision import DecisionPolicy, decide


def decide_batch(
    traces: Sequence[Trace],
    fsm_results: Sequence[FsmResult],
    scores_by_detector: dict[str, Sequence[DetectorScore]],
    policy: str | DecisionPolicy = "any",
    state_names: dict[str, str] | None = None,
) -> list[HybridDecision]:
    """
    Batch hybrid decision pipeline per Doc 14 §7.

    Fuses formal automata validation results with ML detector scores across
    a sequence of traces.

    Args:
        traces: Sequence of Trace objects.
        fsm_results: Sequence of FsmResult objects.
        scores_by_detector: Dictionary mapping detector name -> list of DetectorScore objects.
        policy: Decision policy ('any', 'all', 'primary:<name>' or DecisionPolicy instance).
        state_names: Optional dictionary mapping state IDs to human-readable names.

    Returns:
        list[HybridDecision]: Sequence of hybrid decisions aligned with input traces.
    """
    fsm_by_case: dict[str, FsmResult] = {r.case_id: r for r in fsm_results}

    # Group scores by case_id
    scores_by_case: dict[str, list[DetectorScore]] = defaultdict(list)
    for detector_scores in scores_by_detector.values():
        for s in detector_scores:
            scores_by_case[s.case_id].append(s)

    decisions: list[HybridDecision] = []
    for trace in traces:
        cid = trace.case_id
        fsm = fsm_by_case.get(cid)
        if fsm is None:
            raise KeyError(f"Missing FsmResult for case '{cid}' in batch pipeline.")

        case_scores = scores_by_case.get(cid, [])
        decision = decide(
            fsm=fsm,
            scores=case_scores,
            policy=policy,
            state_names=state_names,
        )
        decisions.append(decision)

    return decisions


def run_hybrid_pipeline(
    traces: Sequence[Trace],
    dfa: DFA,
    detectors: Sequence[AnomalyDetector],
    policy: str | DecisionPolicy = "any",
    state_names: dict[str, str] | None = None,
) -> list[HybridDecision]:
    """
    End-to-end convenience pipeline:
    1. Validates all traces using the formal DFA engine.
    2. Scores all traces across provided ML anomaly detectors.
    3. Executes the hybrid decision matrix and generates explanations.

    Args:
        traces: Sequence of Trace objects.
        dfa: Formal workflow DFA.
        detectors: Sequence of fitted and calibrated AnomalyDetector instances.
        policy: Fusion policy.
        state_names: Optional state names map.

    Returns:
        list[HybridDecision]: Ordered list of hybrid decisions.
    """
    # 1. Formal FSM validation
    fsm_results: list[FsmResult] = [validate_trace(dfa, t.case_id, t.activities) for t in traces]

    # 2. ML Detector scoring
    scores_by_detector: dict[str, list[DetectorScore]] = {}
    for detector in detectors:
        scores_by_detector[detector.name] = detector.score(traces)

    # 3. Decision matrix fusion
    return decide_batch(
        traces=traces,
        fsm_results=fsm_results,
        scores_by_detector=scores_by_detector,
        policy=policy,
        state_names=state_names,
    )
