from collections.abc import Sequence

from src.automata.explain import explain_fsm
from src.common.types import DetectorScore, FinalLabel, FsmResult, FsmVerdict


def explain_ml(score: DetectorScore) -> list[str]:
    """Format human-readable explanation lines for a single firing ML detector."""
    lines = [
        f"Flagged by detector '{score.detector}' (norm_score={score.norm_score:.4f} >= threshold {score.threshold:.4f})."
    ]
    for factor in score.factors:
        lines.append(f"  - {factor.note}")
    return lines


def explain_hybrid(
    fsm: FsmResult,
    scores: Sequence[DetectorScore],
    final_label: FinalLabel,
    ml_flag: bool,
    state_names: dict[str, str] | None = None,
) -> list[str]:
    """
    Synthesize ordered, human-readable explanations for a hybrid decision,
    per Doc 05 §5.3 - §5.4.

    Args:
        fsm: Formal FsmResult from automata validation.
        scores: Sequence of DetectorScore objects from ML detectors.
        final_label: Decided FinalLabel.
        ml_flag: Boolean indicating whether the active ML policy triggered.
        state_names: Optional dictionary mapping state IDs to human-readable names.

    Returns:
        list[str]: Ordered explanatory sentences.
    """
    ml_fired = [s for s in scores if s.is_anomaly]

    if final_label == FinalLabel.RULE_VIOLATION:
        lines = explain_fsm(fsm, state_names=state_names)
        if ml_flag and ml_fired:
            detectors_str = ", ".join(s.detector for s in ml_fired)
            lines.append(f"Also statistically unusual: flagged by ML detectors ({detectors_str}).")
            for s in ml_fired:
                for f in s.factors[:2]:  # Top context factors
                    lines.append(f"  - {s.detector}: {f.note}")
        return lines

    if final_label == FinalLabel.IN_PROGRESS:
        lines = explain_fsm(fsm, state_names=state_names)
        lines.append("ML anomaly detection is not applied to incomplete traces.")
        return lines

    if final_label == FinalLabel.STATISTICAL_ANOMALY:
        lines = ["Trace is valid under the workflow rules (no rule violation)."]
        for s in ml_fired:
            lines.extend(explain_ml(s))
        return lines

    # FinalLabel.NORMAL
    if fsm.verdict == FsmVerdict.VALID_COMPLETE:
        return ["No rule violation; anomaly scores below calibrated thresholds."]
    return ["No rule violation detected."]
