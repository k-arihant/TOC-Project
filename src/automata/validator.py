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

    # Precompute a normalized lookup dict for whitespace-insensitive and case-insensitive matching
    # e.g., "Order Created", "ordercreated", "  OrderCreated  " -> "OrderCreated"
    norm_alphabet: Dict[str, str] = {}
    for canonical in dfa.alphabet:
        norm_alphabet[canonical] = canonical
        norm_alphabet[canonical.strip()] = canonical
        norm_alphabet[canonical.lower()] = canonical
        norm_alphabet[canonical.lower().replace(" ", "")] = canonical
        norm_alphabet[canonical.lower().replace("_", "")] = canonical
        norm_alphabet[canonical.lower().replace("-", "")] = canonical

    for i, raw_event in enumerate(activities):
        cleaned_raw = raw_event.strip() if isinstance(raw_event, str) else str(raw_event)
        
        # 1. Resolve event through activity map if provided
        event = activity_map.get(cleaned_raw, cleaned_raw) if activity_map else cleaned_raw

        # 2. Match against normalized alphabet to tolerate extra spaces or casing variations
        if event in dfa.alphabet:
            canonical_event = event
        else:
            norm_key = event.lower().replace(" ", "").replace("_", "").replace("-", "")
            canonical_event = norm_alphabet.get(norm_key, event)

        # 3. Check if event belongs to the workflow alphabet
        if canonical_event not in dfa.alphabet:
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

        # 4. Check for events after terminal accepting state
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

        # 5. Step through transition function
        q_next = dfa.step(q, canonical_event)

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
