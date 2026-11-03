"""DFA language equivalence check using BFS product exploration and counter-example generation."""

from collections import deque
from typing import Dict, List, Optional, Tuple

from src.automata.dfa import DFA


def equivalent(d1: DFA, d2: DFA) -> Tuple[bool, Optional[List[str]]]:
    """Test if two DFAs accept the exact same language: L(D1) == L(D2).

    Uses BFS on the Cartesian product automaton (D1 x D2). If a symmetric difference
    is reachable (one state is accepting and the other is not), reconstructs and returns
    the shortest witness counter-example string.

    Args:
        d1: First complete DFA.
        d2: Second complete DFA.

    Returns:
        tuple (is_equivalent, counter_example):
          - (True, None) if L(D1) == L(D2)
          - (False, [symbols...]) if languages differ
    """
    c1 = d1.complete() if not d1.is_complete() else d1
    c2 = d2.complete() if not d2.is_complete() else d2

    alphabet = sorted(c1.alphabet | c2.alphabet)
    start_pair = (c1.start_state, c2.start_state)

    queue = deque([start_pair])
    visited = {start_pair}
    parent: Dict[Tuple[str, str], Tuple[Tuple[str, str], str]] = {}

    while queue:
        p, q = queue.popleft()
        p_acc = p in c1.accepting_states
        q_acc = q in c2.accepting_states

        # Symmetric difference: one accepts, the other rejects
        if p_acc != q_acc:
            # Reconstruct the counter-example string by following parent pointers
            counter_example: List[str] = []
            curr = (p, q)
            while curr != start_pair:
                prev_pair, sym = parent[curr]
                counter_example.append(sym)
                curr = prev_pair
            counter_example.reverse()
            return False, counter_example

        for sym in alphabet:
            nxt_p = c1.step(p, sym)
            nxt_q = c2.step(q, sym)
            nxt_pair = (nxt_p, nxt_q)

            if nxt_pair not in visited:
                visited.add(nxt_pair)
                parent[nxt_pair] = ((p, q), sym)
                queue.append(nxt_pair)

    return True, None
