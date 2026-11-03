"""Subset construction algorithm converting an epsilon-NFA to a complete DFA."""

from collections import deque
from typing import Dict, FrozenSet, Set, Tuple

from src.automata.dfa import DFA
from src.automata.nfa import NFA


def nfa_to_dfa_with_subsets(nfa: NFA) -> Tuple[DFA, Dict[str, FrozenSet[str]]]:
    """Convert an epsilon-NFA to a complete DFA using subset construction.

    Returns:
        tuple of (dfa, subset_map) where subset_map maps DFA state names to NFA state subsets.
    """
    start_subset = frozenset(nfa.epsilon_closure({nfa.start_state}))
    worklist = deque([start_subset])

    subset_to_name: Dict[FrozenSet[str], str] = {start_subset: "q0"}
    name_to_subset: Dict[str, FrozenSet[str]] = {"q0": start_subset}
    dfa_delta: Dict[Tuple[str, str], str] = {}
    dfa_accepting: Set[str] = set()

    state_idx = 1
    sorted_alphabet = sorted(nfa.alphabet)

    while worklist:
        curr_subset = worklist.popleft()
        curr_name = subset_to_name[curr_subset]

        # Check if accepting
        if any(q in nfa.accepting_states for q in curr_subset):
            dfa_accepting.add(curr_name)

        # Explore transitions for each symbol
        for sym in sorted_alphabet:
            target_set: Set[str] = set()
            for q in curr_subset:
                target_set.update(nfa.step(q, sym))

            if not target_set:
                continue

            target_subset = frozenset(nfa.epsilon_closure(target_set))

            if target_subset not in subset_to_name:
                target_name = f"q{state_idx}"
                state_idx += 1
                subset_to_name[target_subset] = target_name
                name_to_subset[target_name] = target_subset
                worklist.append(target_subset)

            dfa_delta[(curr_name, sym)] = subset_to_name[target_subset]

    dfa_states = set(subset_to_name.values())
    raw_dfa = DFA(
        states=dfa_states,
        alphabet=set(nfa.alphabet),
        delta=dfa_delta,
        start_state="q0",
        accepting_states=dfa_accepting,
        dead_state="S_dead",
    )

    complete_dfa = raw_dfa.complete()
    name_to_subset[complete_dfa.dead_state] = frozenset()

    return complete_dfa, name_to_subset


def nfa_to_dfa(nfa: NFA) -> DFA:
    """Subset construction converting an epsilon-NFA to an equivalent complete DFA."""
    dfa, _ = nfa_to_dfa_with_subsets(nfa)
    return dfa
