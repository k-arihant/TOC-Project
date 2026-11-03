"""DFA minimization using Moore's partition refinement algorithm."""

from collections import deque
from typing import Dict, List, Set, Tuple

from src.automata.dfa import DFA


def remove_unreachable_states(dfa: DFA) -> DFA:
    """Return a DFA containing only states reachable from the start state."""
    reachable: Set[str] = {dfa.start_state}
    queue = deque([dfa.start_state])

    while queue:
        curr = queue.popleft()
        for sym in dfa.alphabet:
            target = dfa.step(curr, sym)
            if target not in reachable and target in dfa.states:
                reachable.add(target)
                queue.append(target)

    # Filter delta and states
    new_delta = {
        (q, sym): target
        for (q, sym), target in dfa.delta.items()
        if q in reachable and target in reachable
    }
    new_accepting = dfa.accepting_states & reachable
    new_names = {q: dfa.state_names[q] for q in reachable if q in dfa.state_names}

    return DFA(
        states=reachable,
        alphabet=set(dfa.alphabet),
        delta=new_delta,
        start_state=dfa.start_state,
        accepting_states=new_accepting,
        dead_state=dfa.dead_state,
        state_names=new_names,
    )


def minimise(dfa: DFA) -> Tuple[DFA, Dict[str, List[str]]]:
    """Minimise a complete DFA using Moore's partition refinement algorithm.

    Args:
        dfa: A complete DFA.

    Returns:
        tuple of (minimal_dfa, merged_map) where merged_map maps representative
        state names to the list of original states merged into them.
    """
    # 1. First ensure DFA is complete and remove unreachable states
    complete_dfa = dfa.complete() if not dfa.is_complete() else dfa
    clean_dfa = remove_unreachable_states(complete_dfa)

    # 2. Initial partition: Accepting vs Non-Accepting
    f_states = set(clean_dfa.accepting_states)
    non_f_states = set(clean_dfa.states) - f_states

    partition: List[Set[str]] = []
    if f_states:
        partition.append(f_states)
    if non_f_states:
        partition.append(non_f_states)

    sorted_alphabet = sorted(clean_dfa.alphabet)

    # 3. Iterative refinement
    changed = True
    while changed:
        changed = False
        new_partition: List[Set[str]] = []

        # Map each state to its current block index
        state_to_block_idx: Dict[str, int] = {}
        for idx, block in enumerate(partition):
            for state in block:
                state_to_block_idx[state] = idx

        for block in partition:
            if len(block) <= 1:
                new_partition.append(block)
                continue

            # Group states by transition signature: tuple of target block indices
            signatures: Dict[Tuple[int, ...], Set[str]] = {}
            for state in sorted(block):
                sig = tuple(
                    state_to_block_idx.get(clean_dfa.step(state, sym), -1)
                    for sym in sorted_alphabet
                )
                signatures.setdefault(sig, set()).add(state)

            if len(signatures) > 1:
                changed = True
            new_partition.extend(signatures.values())

        partition = new_partition

    # 4. Construct the quotient automaton
    merged_map: Dict[str, List[str]] = {}
    state_to_rep: Dict[str, str] = {}

    for block in partition:
        # Choose representative: prefer dead_state if present, otherwise lexicographical min
        sorted_members = sorted(block)
        if clean_dfa.dead_state in block:
            rep = clean_dfa.dead_state
        else:
            rep = sorted_members[0]

        merged_map[rep] = sorted_members
        for state in block:
            state_to_rep[state] = rep

    new_states = set(merged_map.keys())
    new_start = state_to_rep[clean_dfa.start_state]
    new_accepting = {state_to_rep[q] for q in clean_dfa.accepting_states}
    new_dead = state_to_rep.get(clean_dfa.dead_state, clean_dfa.dead_state)

    new_delta: Dict[Tuple[str, str], str] = {}
    for rep in new_states:
        for sym in sorted_alphabet:
            target = clean_dfa.step(rep, sym)
            new_delta[(rep, sym)] = state_to_rep[target]

    new_names: Dict[str, str] = {}
    for rep, members in merged_map.items():
        if len(members) == 1 and members[0] in clean_dfa.state_names:
            new_names[rep] = clean_dfa.state_names[members[0]]
        else:
            member_names = [clean_dfa.state_names.get(m, m) for m in members]
            new_names[rep] = "/".join(member_names)

    min_dfa = DFA(
        states=new_states,
        alphabet=set(clean_dfa.alphabet),
        delta=new_delta,
        start_state=new_start,
        accepting_states=new_accepting,
        dead_state=new_dead,
        state_names=new_names,
    )

    return min_dfa, merged_map
