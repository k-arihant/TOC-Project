"""Tests for DFA minimization using Moore's algorithm."""

from pathlib import Path

from src.automata.equivalence import equivalent
from src.automata.loader import load_workflow
from src.automata.minimization import minimise

SPEC_PATH = Path("workflows/order_payment/workflow.yaml")


def test_workflow_dfa_minimisation_expected_merges():
    """Verify that Moore minimization merges S1 ≡ S3 and S8 ≡ S11 as predicted in Doc 04 §6."""
    dfa = load_workflow(SPEC_PATH)
    min_dfa, merged_map = minimise(dfa)

    # Original DFA has 14 states (13 live + S_dead)
    assert len(dfa.states) == 14

    # Minimal DFA must have 12 states (11 live + S_dead: exactly 2 merges)
    assert len(min_dfa.states) == 12

    # Find the blocks containing S1, S3, S8, S11
    s1_rep = next(rep for rep, members in merged_map.items() if "S1" in members)
    s3_rep = next(rep for rep, members in merged_map.items() if "S3" in members)
    assert s1_rep == s3_rep, (
        f"Expected S1 and S3 to be merged, but got reps '{s1_rep}' and '{s3_rep}'"
    )
    assert "S1" in merged_map[s1_rep] and "S3" in merged_map[s1_rep]

    s8_rep = next(rep for rep, members in merged_map.items() if "S8" in members)
    s11_rep = next(rep for rep, members in merged_map.items() if "S11" in members)
    assert s8_rep == s11_rep, (
        f"Expected S8 and S11 to be merged, but got reps '{s8_rep}' and '{s11_rep}'"
    )
    assert "S8" in merged_map[s8_rep] and "S11" in merged_map[s8_rep]

    # Verify that original and minimal DFAs are language-equivalent
    is_eq, counter = equivalent(dfa, min_dfa)
    assert is_eq is True, f"Minimal DFA is not language equivalent! Counter-example: {counter}"
