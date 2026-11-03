"""Explanation generation for FSM validation verdicts."""

from typing import Dict, List, Optional

from src.common.types import FsmResult, FsmVerdict


def format_state(state: str, state_names: Optional[Dict[str, str]] = None) -> str:
    """Format state identifier with friendly name if available."""
    if not state_names:
        return state
    name = state_names.get(state)
    return f"{state} ({name})" if name and name != state else state


def explain_fsm(result: FsmResult, state_names: Optional[Dict[str, str]] = None) -> List[str]:
    """Produce deterministic human-readable explanations from an FsmResult.

    Args:
        result: The FsmResult returned by validate_trace.
        state_names: Optional map from state IDs to human-readable names.

    Returns:
        List of explanatory sentences describing the validation outcome.
    """
    if result.verdict == FsmVerdict.VALID_COMPLETE:
        last_state = format_state(result.state_path[-1], state_names)
        return [f"Trace completed successfully in accepting state {last_state}."]

    if result.verdict == FsmVerdict.VALID_PREFIX:
        current_state = format_state(result.state_path[-1], state_names)
        allowed = ", ".join(result.allowed_events) if result.allowed_events else "None"
        return [
            f"Trace is valid so far; current state is {current_state}.",
            f"Allowed next events: {allowed}.",
        ]

    # INVALID cases
    explanations: List[str] = []
    fail_state_desc = format_state(result.fail_state or "Unknown", state_names)

    if result.reason_code == "ILLEGAL_TRANSITION":
        explanations.append(
            f"Event '{result.fail_event}' at position {result.fail_index} is not allowed in state {fail_state_desc}."
        )
        allowed = ", ".join(result.allowed_events) if result.allowed_events else "None"
        explanations.append(f"Allowed events here: {allowed}.")
    elif result.reason_code == "UNKNOWN_EVENT":
        explanations.append(
            f"Event '{result.fail_event}' at position {result.fail_index} is not part of the workflow alphabet."
        )
    elif result.reason_code == "EVENT_AFTER_FINAL":
        explanations.append(
            f"Event '{result.fail_event}' at position {result.fail_index} occurs after terminal closed state {fail_state_desc}."
        )
    else:
        explanations.append(
            f"Invalid transition at position {result.fail_index} with event '{result.fail_event}'."
        )

    # State path history
    formatted_path = [format_state(s, state_names) for s in result.state_path]
    explanations.append(f"Path so far: {' -> '.join(formatted_path)}.")

    return explanations
