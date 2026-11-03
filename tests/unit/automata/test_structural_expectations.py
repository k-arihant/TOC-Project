"""Mandatory test confirming all hand-derived structural expectations from Doc 04 §6."""

from pathlib import Path

from src.automata.equivalence import equivalent
from src.automata.loader import load_workflow
from src.automata.minimization import minimise
from src.automata.reachability import analyse

SPEC_PATH = Path("workflows/order_payment/workflow.yaml")


def test_structural_expectations_table_doc04_section_6():
    """Verify all 8 structural expectations from Doc 04 §6.

    If any expectation does not hold, the assertion message explains the exact discrepancy.
    Do not weaken this test.
    """
    dfa = load_workflow(SPEC_PATH)
    min_dfa, merged_map = minimise(dfa)
    report = analyse(dfa)

    live_states = dfa.states - {dfa.dead_state}

    # 1. Live states in hand-designed DFA: expected 13 (S0..S12)
    assert len(live_states) == 13, (
        f"Expected exactly 13 live states (S0..S12), but found {len(live_states)}: {sorted(live_states)}"
    )

    # 2. Complete DFA including S_dead: expected 14 states
    assert len(dfa.states) == 14, (
        f"Expected complete DFA to have 14 states (13 live + S_dead), but found {len(dfa.states)}: {sorted(dfa.states)}"
    )

    # 3. Equivalent pairs: S1 ≡ S3 and S8 ≡ S11
    s1_rep = next(rep for rep, members in merged_map.items() if "S1" in members)
    s3_rep = next(rep for rep, members in merged_map.items() if "S3" in members)
    assert s1_rep == s3_rep, (
        f"Expected S1 (Created) ≡ S3 (PaymentFailed) under Myhill-Nerode equivalence, "
        f"but S1 mapped to '{s1_rep}' and S3 mapped to '{s3_rep}'."
    )

    s8_rep = next(rep for rep, members in merged_map.items() if "S8" in members)
    s11_rep = next(rep for rep, members in merged_map.items() if "S11" in members)
    assert s8_rep == s11_rep, (
        f"Expected S8 (CancelledUnpaid) ≡ S11 (Refunded) under Myhill-Nerode equivalence, "
        f"but S8 mapped to '{s8_rep}' and S11 mapped to '{s11_rep}'."
    )

    # 4. Minimal complete DFA: expected 12 states (11 live + S_dead)
    assert len(min_dfa.states) == 12, (
        f"Expected minimal complete DFA to have 12 states (14 - 2 merges), "
        f"but found {len(min_dfa.states)}: {sorted(min_dfa.states)}"
    )

    # 5. Reachable states from S0: expected all 13 live states
    assert live_states.issubset(report.reachable), (
        f"Expected all 13 live states to be reachable from S0, "
        f"but unreachable live states found: {live_states - report.reachable}"
    )

    # 6. Dead (non-co-reachable) live states: expected none (only S_dead cannot reach F)
    dead_live_states = report.dead - {dfa.dead_state}
    assert len(dead_live_states) == 0, (
        f"Expected no dead live states, but found: {dead_live_states}"
    )

    # 7. Unreachable states: expected none
    assert len(report.unreachable) == 0, (
        f"Expected 0 unreachable states, but found: {report.unreachable}"
    )

    # 8. Original DFA vs Minimal DFA language equivalence
    is_eq, counter = equivalent(dfa, min_dfa)
    assert is_eq is True, (
        f"Expected original DFA and minimal DFA to be language-equivalent, "
        f"but equivalence check failed with counter-example: {counter}"
    )
