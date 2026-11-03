"""Tests for automata explanation formatting and DOT generation."""
from pathlib import Path

from src.automata.explain import explain_fsm
from src.automata.loader import load_workflow
from src.automata.validator import validate_trace
from src.automata.visualize import to_dot

SPEC_PATH = Path("workflows/order_payment/workflow.yaml")


def test_explain_fsm_illegal_transition():
    dfa = load_workflow(SPEC_PATH)
    result = validate_trace(
        dfa, "c1", ["OrderCreated", "PaymentInitiated", "PaymentAuthorized", "OrderShipped"]
    )

    explanations = explain_fsm(result, dfa.state_names)
    assert len(explanations) >= 2
    assert "Event 'OrderShipped' at position 3 is not allowed" in explanations[0]
    assert "OrderPacked" in explanations[1] and "OrderCancelled" in explanations[1]


def test_explain_fsm_valid_complete():
    dfa = load_workflow(SPEC_PATH)
    result = validate_trace(
        dfa,
        "c2",
        [
            "OrderCreated",
            "PaymentInitiated",
            "PaymentAuthorized",
            "OrderPacked",
            "OrderShipped",
            "OrderDelivered",
            "OrderClosed",
        ],
    )

    explanations = explain_fsm(result, dfa.state_names)
    assert len(explanations) == 1
    assert "Trace completed successfully in accepting state S12 (Closed)" in explanations[0]


def test_to_dot_generation():
    dfa = load_workflow(SPEC_PATH)
    dot = to_dot(dfa, highlight_path=["S0", "S1"], fail_edge=("S1", "OrderShipped", "S_dead"))

    assert "digraph WorkflowDFA" in dot
    assert '"S0" -> "S1"' in dot
    assert "#d62728" in dot  # Red highlight color present
