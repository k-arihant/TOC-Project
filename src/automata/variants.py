"""Automata variants demonstrating theoretical regular language properties."""

from typing import Dict, Set, Tuple

from src.automata.dfa import DFA


def bounded_retry_dfa(k: int = 3) -> DFA:
    """Construct a bounded-retry DFA allowing at most k payment attempts (Doc 04 §8).

    States:
      - S0 (Start), S1 (Created)
      - S2_1..S2_k (PaymentPending for attempt 1..k)
      - S3_1..S3_k (PaymentFailed for attempt 1..k)
      - S4..S12 (Downstream lifecycle states)
      - S_dead (Trap state)

    Key regular property demonstrated:
      - Fixed counting (at most k retries) is regular, but state count grows O(k).
      - L(DFA_k) is a strict subset of L(M_unbounded).
    """
    if k < 1:
        raise ValueError("k must be at least 1.")

    states: Set[str] = {
        "S0",
        "S1",
        "S4",
        "S5",
        "S6",
        "S7",
        "S8",
        "S9",
        "S10",
        "S11",
        "S12",
        "S_dead",
    }
    state_names: Dict[str, str] = {
        "S0": "Start",
        "S1": "Created",
        "S4": "Paid",
        "S5": "Packed",
        "S6": "Shipped",
        "S7": "Delivered",
        "S8": "CancelledUnpaid",
        "S9": "CancelledPaid",
        "S10": "RefundPending",
        "S11": "Refunded",
        "S12": "Closed",
        "S_dead": "Dead",
    }

    for i in range(1, k + 1):
        s2_i = f"S2_{i}"
        s3_i = f"S3_{i}"
        states.add(s2_i)
        states.add(s3_i)
        state_names[s2_i] = f"PaymentPending_attempt_{i}"
        state_names[s3_i] = f"PaymentFailed_attempt_{i}"

    alphabet: Set[str] = {
        "OrderCreated",
        "PaymentInitiated",
        "PaymentAuthorized",
        "PaymentFailed",
        "OrderPacked",
        "OrderShipped",
        "OrderDelivered",
        "OrderCancelled",
        "RefundRequested",
        "RefundCompleted",
        "OrderClosed",
    }

    delta: Dict[Tuple[str, str], str] = {}

    # Initial flow
    delta[("S0", "OrderCreated")] = "S1"
    delta[("S1", "PaymentInitiated")] = "S2_1"
    delta[("S1", "OrderCancelled")] = "S8"

    # Payment attempts 1..k
    for i in range(1, k + 1):
        s2_i = f"S2_{i}"
        s3_i = f"S3_{i}"

        delta[(s2_i, "PaymentAuthorized")] = "S4"
        delta[(s2_i, "PaymentFailed")] = s3_i
        delta[(s3_i, "OrderCancelled")] = "S8"

        # Retry transition only allowed up to k-1 (attempt k has no PI edge)
        if i < k:
            s2_next = f"S2_{i + 1}"
            delta[(s3_i, "PaymentInitiated")] = s2_next

    # Downstream flow (identical to base workflow)
    delta[("S4", "OrderPacked")] = "S5"
    delta[("S4", "OrderCancelled")] = "S9"
    delta[("S5", "OrderShipped")] = "S6"
    delta[("S5", "OrderCancelled")] = "S9"
    delta[("S6", "OrderDelivered")] = "S7"
    delta[("S7", "RefundRequested")] = "S10"
    delta[("S7", "OrderClosed")] = "S12"
    delta[("S8", "OrderClosed")] = "S12"
    delta[("S9", "RefundRequested")] = "S10"
    delta[("S10", "RefundCompleted")] = "S11"
    delta[("S11", "OrderClosed")] = "S12"

    dfa = DFA(
        states=states,
        alphabet=alphabet,
        delta=delta,
        start_state="S0",
        accepting_states={"S12"},
        dead_state="S_dead",
        state_names=state_names,
    )

    return dfa.complete()
