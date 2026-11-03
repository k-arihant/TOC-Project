"""Linear-time O(n) trace validator running an event sequence against a DFA."""

from collections.abc import Sequence
from typing import Dict, List, Optional

from src.automata.dfa import DFA
from src.common.types import FsmResult, FsmVerdict


def validate_trace(
    dfa: DFA,
    case_id: str,
    activities: Sequence[str],
    activity_map: Optional[Dict[str, str]] = None,
) -> FsmResult:
    """Validate an activity trace against a DFA in O(n) time and O(n) space.

    Args:
        dfa: Complete DFA with explicit dead state.
        case_id: Identifier of the process case.
        activities: Ordered sequence of activity names or symbol codes.
        activity_map: Optional mapping from abbreviations/synonyms to canonical alphabet names.

    Returns:
        FsmResult containing verdict, visited state path, and failure diagnostics if invalid.
    """
    q = dfa.start_state
    path: List[str] = [q]

    for i, raw_event in enumerate(activities):
        # 1. Resolve event through activity map if provided
        event = activity_map.get(raw_event, raw_event) if activity_map else raw_event

        # 2. Check if event belongs to the workflow alphabet
        if event not in dfa.alphabet:
            return FsmResult(
                case_id=case_id,
                verdict=FsmVerdict.INVALID,
                state_path=path,
                fail_index=i,
                fail_state=q,
                fail_event=raw_event,
                allowed_events=dfa.allowed_events(q),
                reason_code="UNKNOWN_EVENT",
            )

        # 3. Check for events after terminal accepting state
        if q in dfa.accepting_states and not dfa.allowed_events(q):
            return FsmResult(
                case_id=case_id,
                verdict=FsmVerdict.INVALID,
                state_path=path,
                fail_index=i,
                fail_state=q,
                fail_event=raw_event,
                allowed_events=[],
                reason_code="EVENT_AFTER_FINAL",
            )

        # 4. Step through transition function
        q_next = dfa.step(q, event)

        # 5. Check if transition leads to the dead/trap state
        if q_next == dfa.dead_state:
            return FsmResult(
                case_id=case_id,
                verdict=FsmVerdict.INVALID,
                state_path=path,
                fail_index=i,
                fail_state=q,
                fail_event=raw_event,
                allowed_events=dfa.allowed_events(q),
                reason_code="ILLEGAL_TRANSITION",
            )

        q = q_next
        path.append(q)

    # 6. Trace finished all events legally: determine if complete or valid prefix
    verdict = FsmVerdict.VALID_COMPLETE if q in dfa.accepting_states else FsmVerdict.VALID_PREFIX
    return FsmResult(case_id=case_id, verdict=verdict, state_path=path)
