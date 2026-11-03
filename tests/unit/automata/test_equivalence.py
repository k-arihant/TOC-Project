"""Tests for DFA language equivalence checking and counter-example generation."""

from pathlib import Path

from src.automata.dfa import DFA
from src.automata.equivalence import equivalent
from src.automata.loader import load_workflow
from src.automata.minimization import minimise

SPEC_PATH = Path("workflows/order_payment/workflow.yaml")


def test_identical_and_minimised_dfas_equivalent():
    dfa = load_workflow(SPEC_PATH)
    min_dfa, _ = minimise(dfa)

    is_eq, counter = equivalent(dfa, dfa)
    assert is_eq is True
    assert counter is None

    is_eq, counter = equivalent(dfa, min_dfa)
    assert is_eq is True
    assert counter is None


def test_inequivalent_dfas_return_valid_counter_example():
    dfa = load_workflow(SPEC_PATH)

    # Create a mutant DFA where initial OrderCreated leads directly to S12 (Closed)
    mutant_delta = dict(dfa.delta)
    mutant_delta[("S0", "OrderCreated")] = "S12"

    mutant_dfa = DFA(
        states=set(dfa.states),
        alphabet=set(dfa.alphabet),
        delta=mutant_delta,
        start_state=dfa.start_state,
        accepting_states=set(dfa.accepting_states),
        dead_state=dfa.dead_state,
    )

    is_eq, counter = equivalent(dfa, mutant_dfa)
    assert is_eq is False
    assert counter is not None

    # The counter-example string must have different acceptance between the two DFAs
    assert dfa.accepts(counter) != mutant_dfa.accepts(counter)
