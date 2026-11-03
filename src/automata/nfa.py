"""Non-deterministic Finite Automaton with epsilon transitions (epsilon-NFA) and Thompson combinators."""

from dataclasses import dataclass
from typing import Dict, Set, Tuple


@dataclass
class NFA:
    states: Set[str]
    alphabet: Set[str]
    delta: Dict[Tuple[str, str], Set[str]]  # (state, symbol_or_eps) -> set of states
    start_state: str
    accepting_states: Set[str]
    epsilon: str = "ε"

    def epsilon_closure(self, states: Set[str]) -> Set[str]:
        """Compute the epsilon-closure of a set of states."""
        closure = set(states)
        stack = list(states)

        while stack:
            curr = stack.pop()
            epsilon_targets = self.delta.get((curr, self.epsilon), set())
            for target in epsilon_targets:
                if target not in closure:
                    closure.add(target)
                    stack.append(target)

        return closure

    def step(self, state: str, symbol: str) -> Set[str]:
        """Return direct targets for state on symbol."""
        return self.delta.get((state, symbol), set())


# =========================================================================
# Thompson-style NFA Combinators
# =========================================================================

_state_counter = 0


def _new_state(prefix: str = "n") -> str:
    global _state_counter
    _state_counter += 1
    return f"{prefix}_{_state_counter}"


def epsilon_nfa(eps: str = "ε") -> NFA:
    """NFA accepting the empty string ε."""
    s0 = _new_state("eps_start")
    s1 = _new_state("eps_acc")
    return NFA(
        states={s0, s1},
        alphabet=set(),
        delta={(s0, eps): {s1}},
        start_state=s0,
        accepting_states={s1},
        epsilon=eps,
    )


def symbol_nfa(a: str, eps: str = "ε") -> NFA:
    """NFA accepting a single symbol a."""
    s0 = _new_state(f"s_{a}_start")
    s1 = _new_state(f"s_{a}_acc")
    return NFA(
        states={s0, s1},
        alphabet={a},
        delta={(s0, a): {s1}},
        start_state=s0,
        accepting_states={s1},
        epsilon=eps,
    )


def concat_nfa(a: NFA, b: NFA) -> NFA:
    """Concatenation: L(A) . L(B). Connects each accepting state of A to start of B via epsilon."""
    eps = a.epsilon
    states = set(a.states) | set(b.states)
    alphabet = set(a.alphabet) | set(b.alphabet)
    delta: Dict[Tuple[str, str], Set[str]] = {}

    for k, v in a.delta.items():
        delta[k] = set(v)
    for k, v in b.delta.items():
        delta.setdefault(k, set()).update(v)

    # Link accepting states of A to start of B
    for acc in a.accepting_states:
        delta.setdefault((acc, eps), set()).add(b.start_state)

    return NFA(
        states=states,
        alphabet=alphabet,
        delta=delta,
        start_state=a.start_state,
        accepting_states=set(b.accepting_states),
        epsilon=eps,
    )


def union_nfa(a: NFA, b: NFA) -> NFA:
    """Union: L(A) | L(B). Adds new start state branching via epsilon to both starts."""
    eps = a.epsilon
    new_start = _new_state("union_start")
    new_acc = _new_state("union_acc")

    states = set(a.states) | set(b.states) | {new_start, new_acc}
    alphabet = set(a.alphabet) | set(b.alphabet)
    delta: Dict[Tuple[str, str], Set[str]] = {}

    for k, v in a.delta.items():
        delta[k] = set(v)
    for k, v in b.delta.items():
        delta.setdefault(k, set()).update(v)

    delta[(new_start, eps)] = {a.start_state, b.start_state}
    for acc in a.accepting_states:
        delta.setdefault((acc, eps), set()).add(new_acc)
    for acc in b.accepting_states:
        delta.setdefault((acc, eps), set()).add(new_acc)

    return NFA(
        states=states,
        alphabet=alphabet,
        delta=delta,
        start_state=new_start,
        accepting_states={new_acc},
        epsilon=eps,
    )


def star_nfa(a: NFA) -> NFA:
    """Kleene Star: L(A)*. Loops accepting states back to start, and allows skipping."""
    eps = a.epsilon
    new_start = _new_state("star_start")
    new_acc = _new_state("star_acc")

    states = set(a.states) | {new_start, new_acc}
    delta: Dict[Tuple[str, str], Set[str]] = {}

    for k, v in a.delta.items():
        delta[k] = set(v)

    delta[(new_start, eps)] = {a.start_state, new_acc}
    for acc in a.accepting_states:
        delta.setdefault((acc, eps), set()).update({a.start_state, new_acc})

    return NFA(
        states=states,
        alphabet=set(a.alphabet),
        delta=delta,
        start_state=new_start,
        accepting_states={new_acc},
        epsilon=eps,
    )


# =========================================================================
# Canonical Benchmark NFAs from Documentation
# =========================================================================


def build_payment_block_nfa() -> NFA:
    """Construct canonical worked-example NFA from Doc 04 §4.2: PI (PF PI)* PA.

    Explicit state graph:
      a --PI--> b
      b --ε--> c
      c --PF--> d
      d --PI--> b
      b --PA--> e
    """
    states = {"a", "b", "c", "d", "e"}
    alphabet = {"PI", "PF", "PA"}
    delta = {
        ("a", "PI"): {"b"},
        ("b", "ε"): {"c"},
        ("c", "PF"): {"d"},
        ("d", "PI"): {"b"},
        ("b", "PA"): {"e"},
    }
    return NFA(
        states=states,
        alphabet=alphabet,
        delta=delta,
        start_state="a",
        accepting_states={"e"},
        epsilon="ε",
    )
