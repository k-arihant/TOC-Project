"""Unit tests for the DFA core data structure."""

import pytest

from src.automata.dfa import DFA


def test_dfa_creation_and_validation():
    dfa = DFA(
        states={"S0", "S1", "S_dead"},
        alphabet={"a", "b"},
        delta={("S0", "a"): "S1"},
        start_state="S0",
        accepting_states={"S1"},
        dead_state="S_dead",
    )
    assert dfa.start_state == "S0"
    assert dfa.accepts(["a"]) is True
    assert dfa.accepts(["b"]) is False
    assert dfa.accepts(["a", "b"]) is False


def test_dfa_invalid_definition_raises():
    with pytest.raises(ValueError, match="Start state 'Invalid' is not in states"):
        DFA(
            states={"S0"},
            alphabet={"a"},
            delta={},
            start_state="Invalid",
            accepting_states=set(),
        )

    with pytest.raises(ValueError, match="Accepting states.*not in states"):
        DFA(
            states={"S0"},
            alphabet={"a"},
            delta={},
            start_state="S0",
            accepting_states={"S_unknown"},
        )


def test_dfa_completion():
    dfa = DFA(
        states={"S0", "S1"},
        alphabet={"a", "b"},
        delta={("S0", "a"): "S1"},
        start_state="S0",
        accepting_states={"S1"},
        dead_state="S_dead",
    )
    assert not dfa.is_complete()
    complete = dfa.complete()
    assert complete.is_complete()
    assert "S_dead" in complete.states
    assert complete.step("S0", "b") == "S_dead"
    assert complete.step("S1", "a") == "S_dead"
    assert complete.step("S_dead", "a") == "S_dead"
