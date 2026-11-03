"""Tests for reachability analysis and seeded specification defect detection."""

from pathlib import Path

from src.automata.dfa import DFA
from src.automata.loader import load_workflow
from src.automata.reachability import analyse, can_event_occur

SPEC_PATH = Path("workflows/order_payment/workflow.yaml")


def test_workflow_dfa_reachability_normal():
    dfa = load_workflow(SPEC_PATH)
    report = analyse(dfa)

    live_states = dfa.states - {dfa.dead_state}

    # 1. All 13 live states must be reachable from S0
    assert report.reachable == dfa.states
    assert report.unreachable == set()

    # 2. Only S_dead must be dead (non-coreachable)
    assert report.dead == {dfa.dead_state}

    # 3. All 13 live states must be useful (reachable AND coreachable)
    assert report.useful == live_states

    # 4. Shortest paths computed to all states
    assert "S0" in report.shortest_paths
    assert report.shortest_paths["S0"] == []
    assert report.shortest_paths["S1"] == ["OrderCreated"]


def test_seeded_spec_defect_unreachable_orphan_state():
    """Spec-defect test (Doc 04 §7): an orphan state with no incoming edges must be flagged."""
    base_dfa = load_workflow(SPEC_PATH)

    defective_states = set(base_dfa.states) | {"S_orphan"}
    defective_dfa = DFA(
        states=defective_states,
        alphabet=set(base_dfa.alphabet),
        delta=dict(base_dfa.delta),
        start_state=base_dfa.start_state,
        accepting_states=set(base_dfa.accepting_states),
        dead_state=base_dfa.dead_state,
    )

    report = analyse(defective_dfa)
    assert "S_orphan" in report.unreachable


def test_seeded_spec_defect_dead_live_state():
    """Spec-defect test (Doc 04 §7): a live reachable state that cannot reach Closed must be flagged as dead."""
    base_dfa = load_workflow(SPEC_PATH)

    # Add S_limbo: S1 -PI-> S_limbo, but S_limbo only loops on itself and has no path to Closed
    defective_states = set(base_dfa.states) | {"S_limbo"}
    defective_delta = dict(base_dfa.delta)
    defective_delta[("S1", "PaymentInitiated")] = "S_limbo"
    defective_delta[("S_limbo", "PaymentInitiated")] = "S_limbo"

    defective_dfa = DFA(
        states=defective_states,
        alphabet=set(base_dfa.alphabet),
        delta=defective_delta,
        start_state=base_dfa.start_state,
        accepting_states=set(base_dfa.accepting_states),
        dead_state=base_dfa.dead_state,
    )

    report = analyse(defective_dfa)
    assert "S_limbo" in report.reachable
    assert "S_limbo" in report.dead


def test_can_event_occur_utility():
    dfa = load_workflow(SPEC_PATH)
    assert can_event_occur(dfa, "OrderCreated") is True
    assert can_event_occur(dfa, "OrderShipped") is True
    assert can_event_occur(dfa, "RefundCompleted") is True
    assert can_event_occur(dfa, "NonExistentEvent") is False
