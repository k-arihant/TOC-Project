"""Tests for NFA representation, Thompson combinators, and subset construction."""

from src.automata.conversion import nfa_to_dfa, nfa_to_dfa_with_subsets
from src.automata.minimization import minimise
from src.automata.nfa import (
    build_payment_block_nfa,
    concat_nfa,
    star_nfa,
    symbol_nfa,
    union_nfa,
)


def test_thompson_combinators_acceptance():
    # Construct regex: (a | b)* c
    na = symbol_nfa("a")
    nb = symbol_nfa("b")
    nc = symbol_nfa("c")

    ab_union = union_nfa(na, nb)
    ab_star = star_nfa(ab_union)
    regex_nfa = concat_nfa(ab_star, nc)

    dfa = nfa_to_dfa(regex_nfa)

    assert dfa.accepts(["c"]) is True
    assert dfa.accepts(["a", "c"]) is True
    assert dfa.accepts(["b", "c"]) is True
    assert dfa.accepts(["a", "b", "a", "b", "c"]) is True
    assert dfa.accepts(["a", "b"]) is False
    assert dfa.accepts(["c", "a"]) is False


def test_worked_example_doc04_section_4_2():
    """Reproduce worked example from Doc 04 §4.2: Payment Block PI (PF PI)* PA."""
    nfa = build_payment_block_nfa()

    # 1. Verify epsilon-closures
    assert nfa.epsilon_closure({"a"}) == {"a"}
    assert nfa.epsilon_closure({"b"}) == {"b", "c"}
    assert nfa.epsilon_closure({"d"}) == {"d"}
    assert nfa.epsilon_closure({"e"}) == {"e"}

    # 2. Subset construction
    dfa, subset_map = nfa_to_dfa_with_subsets(nfa)

    # Expected live states: {a}, {b,c}, {d}, {e}
    live_subsets = [s for q, s in subset_map.items() if s]
    assert len(live_subsets) == 4
    assert frozenset({"a"}) in live_subsets
    assert frozenset({"b", "c"}) in live_subsets
    assert frozenset({"d"}) in live_subsets
    assert frozenset({"e"}) in live_subsets

    # 3. String acceptance under subset DFA
    assert dfa.accepts(["PI", "PA"]) is True
    assert dfa.accepts(["PI", "PF", "PI", "PA"]) is True
    assert dfa.accepts(["PI", "PF", "PI", "PF", "PI", "PA"]) is True
    assert dfa.accepts(["PI", "PF", "PA"]) is False
    assert dfa.accepts(["PA"]) is False

    # 4. Minimisation of payment block
    min_dfa, merged = minimise(dfa)
    # A {a} and C {d} are Myhill-Nerode equivalent -> minimal DFA has 3 live states + dead state
    live_states = min_dfa.states - {min_dfa.dead_state}
    assert len(live_states) == 3

    # Check language preservation
    assert min_dfa.accepts(["PI", "PF", "PI", "PA"]) is True
    assert min_dfa.accepts(["PI", "PF", "PA"]) is False
