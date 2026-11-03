"""Reachability and dead-state analysis for workflow DFAs."""

from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple

from src.automata.dfa import DFA


@dataclass
class ReachabilityReport:
    reachable: Set[str]
    unreachable: Set[str]
    coreachable: Set[str]
    dead: Set[str]
    useful: Set[str]
    shortest_paths: Dict[str, List[str]]  # state -> list of symbols from start


def analyse(dfa: DFA) -> ReachabilityReport:
    """Analyze reachability, co-reachability, trap states, and shortest paths.

    Definitions (Doc 04 §7):
      - Reachable: reachable from start_state.
      - Unreachable: not reachable from start_state (indicates spec defect).
      - Co-reachable: can reach at least one accepting state.
      - Dead (trap): cannot reach any accepting state (S_dead is expected; other dead states indicate spec defects).
      - Useful: reachable AND co-reachable.

    Returns:
        ReachabilityReport dataclass.
    """
    complete_dfa = dfa.complete() if not dfa.is_complete() else dfa
    all_states = set(complete_dfa.states)

    # 1. Forward BFS from start_state
    reachable: Set[str] = {complete_dfa.start_state}
    forward_queue = deque([complete_dfa.start_state])
    parent: Dict[str, Tuple[str, str]] = {}
    shortest_paths: Dict[str, List[str]] = {complete_dfa.start_state: []}

    while forward_queue:
        curr = forward_queue.popleft()
        for sym in sorted(complete_dfa.alphabet):
            target = complete_dfa.step(curr, sym)
            if target in all_states and target not in reachable:
                reachable.add(target)
                parent[target] = (curr, sym)
                # Reconstruct path
                path = list(shortest_paths[curr]) + [sym]
                shortest_paths[target] = path
                forward_queue.append(target)

    unreachable = all_states - reachable

    # 2. Build reverse graph over non-dead transitions
    reverse_graph: Dict[str, Set[Tuple[str, str]]] = {q: set() for q in all_states}
    for (src, sym), dst in complete_dfa.delta.items():
        reverse_graph.setdefault(dst, set()).add((src, sym))

    # 3. Backward BFS from accepting states
    coreachable: Set[str] = set(complete_dfa.accepting_states)
    backward_queue = deque(list(complete_dfa.accepting_states))

    while backward_queue:
        curr = backward_queue.popleft()
        for prev_state, _sym in reverse_graph.get(curr, set()):
            if prev_state not in coreachable and prev_state in all_states:
                coreachable.add(prev_state)
                backward_queue.append(prev_state)

    dead = all_states - coreachable
    useful = reachable & coreachable

    return ReachabilityReport(
        reachable=reachable,
        unreachable=unreachable,
        coreachable=coreachable,
        dead=dead,
        useful=useful,
        shortest_paths=shortest_paths,
    )


def can_event_occur(dfa: DFA, event: str) -> bool:
    """Test if an event can ever occur in any reachable valid execution."""
    report = analyse(dfa)
    for q in report.reachable:
        if q == dfa.dead_state:
            continue
        target = dfa.step(q, event)
        if target != dfa.dead_state and target in report.coreachable:
            return True
    return False
