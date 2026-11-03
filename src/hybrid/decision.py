from collections.abc import Sequence

from src.common.types import DetectorScore, FinalLabel, FsmResult, FsmVerdict, HybridDecision
from src.hybrid.explanation import explain_hybrid


class DecisionPolicy:
    """
    Evaluates ML detector scores against a configured policy, per Doc 05 §5.2:
    - 'any': True if ANY configured detector flagged an anomaly (default)
    - 'all': True if ALL configured detectors flagged an anomaly
    - 'primary:<detector>': True if the specified primary detector flagged an anomaly
    """

    def __init__(
        self,
        policy: str = "any",
        detector_names: Sequence[str] | None = None,
    ) -> None:
        self.raw_policy = policy.strip()
        self.detector_names = set(detector_names) if detector_names is not None else None

        if self.raw_policy in ("any", "all"):
            self.mode = self.raw_policy
            self.primary_detector = None
        elif self.raw_policy.startswith("primary:"):
            self.mode = "primary"
            self.primary_detector = self.raw_policy.split(":", 1)[1].strip()
        else:
            raise ValueError(
                f"Unknown decision policy '{policy}'. Must be 'any', 'all', or 'primary:<detector>'."
            )

    def apply(self, scores: Sequence[DetectorScore]) -> bool:
        """
        Evaluate scores according to the policy.

        Args:
            scores: Sequence of DetectorScore objects.

        Returns:
            bool: True if policy conditions are met (ML flag triggers).
        """
        # Filter scores by configured detector names if specified
        relevant_scores = [
            s for s in scores if self.detector_names is None or s.detector in self.detector_names
        ]

        if not relevant_scores:
            return False

        if self.mode == "any":
            return any(s.is_anomaly for s in relevant_scores)

        if self.mode == "all":
            return all(s.is_anomaly for s in relevant_scores)

        if self.mode == "primary":
            for s in relevant_scores:
                if s.detector == self.primary_detector:
                    return s.is_anomaly
            return False

        return False


def decide(
    fsm: FsmResult,
    scores: Sequence[DetectorScore],
    policy: str | DecisionPolicy = "any",
    state_names: dict[str, str] | None = None,
) -> HybridDecision:
    """
    Execute hybrid fusion decision table per Doc 05 §5.1 & §5.3.

    Decision Table:
    1. FSM == INVALID       -> RULE_VIOLATION (ML evidence preserved in explanations/context)
    2. FSM == VALID_PREFIX  -> IN_PROGRESS (ML not applied to incomplete traces)
    3. FSM == VALID_COMPLETE & ML flag == True  -> STATISTICAL_ANOMALY
    4. FSM == VALID_COMPLETE & ML flag == False -> NORMAL

    Args:
        fsm: Formal FsmResult from automata validation.
        scores: Sequence of DetectorScore objects from ML detectors.
        policy: Policy instance or policy name ('any', 'all', 'primary:<name>').
        state_names: Optional dictionary mapping state IDs to human-readable names.

    Returns:
        HybridDecision: Complete hybrid decision with final label and explanations.
    """
    policy_obj = policy if isinstance(policy, DecisionPolicy) else DecisionPolicy(policy)
    ml_flag = policy_obj.apply(scores)

    if fsm.verdict == FsmVerdict.INVALID:
        final_label = FinalLabel.RULE_VIOLATION
    elif fsm.verdict == FsmVerdict.VALID_PREFIX:
        final_label = FinalLabel.IN_PROGRESS
    elif ml_flag:
        final_label = FinalLabel.STATISTICAL_ANOMALY
    else:
        final_label = FinalLabel.NORMAL

    explanation = explain_hybrid(
        fsm=fsm,
        scores=scores,
        final_label=final_label,
        ml_flag=ml_flag,
        state_names=state_names,
    )

    return HybridDecision(
        case_id=fsm.case_id,
        final_label=final_label,
        fsm=fsm,
        ml=list(scores),
        explanation=explanation,
    )
