"""Automata module for TOC engine: DFA, NFA, minimization, reachability, validation."""

from src.automata.dfa import DFA
from src.automata.equivalence import equivalent
from src.automata.explain import explain_fsm
from src.automata.loader import load_workflow
from src.automata.minimization import minimise
from src.automata.nfa import NFA
from src.automata.reachability import analyse, can_event_occur
from src.automata.validator import validate_trace
from src.automata.variants import bounded_retry_dfa
from src.automata.visualize import to_dot

__all__ = [
    "DFA",
    "NFA",
    "load_workflow",
    "validate_trace",
    "explain_fsm",
    "minimise",
    "equivalent",
    "analyse",
    "can_event_occur",
    "to_dot",
    "bounded_retry_dfa",
]
