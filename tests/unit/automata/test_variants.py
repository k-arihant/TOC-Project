"""Tests for bounded-retry DFA variants (Doc 04 §8)."""

from pathlib import Path

from src.automata.loader import load_workflow
from src.automata.variants import bounded_retry_dfa

SPEC_PATH = Path("workflows/order_payment/workflow.yaml")


def test_bounded_retry_limits():
    k = 2
    b_dfa = bounded_retry_dfa(k=k)

    # 0 retries: accepted
    assert (
        b_dfa.accepts(
            [
                "OrderCreated",
                "PaymentInitiated",
                "PaymentAuthorized",
                "OrderPacked",
                "OrderShipped",
                "OrderDelivered",
                "OrderClosed",
            ]
        )
        is True
    )

    # 1 retry: accepted
    assert (
        b_dfa.accepts(
            [
                "OrderCreated",
                "PaymentInitiated",
                "PaymentFailed",
                "PaymentInitiated",
                "PaymentAuthorized",
                "OrderPacked",
                "OrderShipped",
                "OrderDelivered",
                "OrderClosed",
            ]
        )
        is True
    )

    # 2 retries (total 3 attempts): rejected when k=2 (since k=2 allows max 2 attempts)
    # Attempt 1: PI -> Failed
    # Attempt 2: Retry PI -> Failed
    # Attempt 3: Retry PI -> Rejected!
    two_retries_string = [
        "OrderCreated",
        "PaymentInitiated",
        "PaymentFailed",
        "PaymentInitiated",
        "PaymentFailed",
        "PaymentInitiated",
        "PaymentAuthorized",
        "OrderPacked",
        "OrderShipped",
        "OrderDelivered",
        "OrderClosed",
    ]
    assert b_dfa.accepts(two_retries_string) is False


def test_bounded_retry_is_strict_subset_of_unbounded_dfa():
    base_dfa = load_workflow(SPEC_PATH)
    b_dfa = bounded_retry_dfa(k=2)

    # A trace with 4 payment attempts (3 retries) is accepted by unbounded DFA, but rejected by bounded DFA
    excessive_retries_trace = [
        "OrderCreated",
        "PaymentInitiated",
        "PaymentFailed",
        "PaymentInitiated",
        "PaymentFailed",
        "PaymentInitiated",
        "PaymentFailed",
        "PaymentInitiated",
        "PaymentAuthorized",
        "OrderPacked",
        "OrderShipped",
        "OrderDelivered",
        "OrderClosed",
    ]
    assert base_dfa.accepts(excessive_retries_trace) is True
    assert b_dfa.accepts(excessive_retries_trace) is False
