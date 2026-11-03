"""Deterministic Finite Automaton (DFA) data structure, completion, and simulation."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple


@dataclass
class DFA:
    states: Set[str]
    alphabet: Set[str]
    delta: Dict[Tuple[str, str], str]  # (from_state, symbol) -> to_state
    start_state: str
    accepting_states: Set[str]
    dead_state: str = "S_dead"
    state_names: Dict[str, str] = field(default_factory=dict)  # state_id -> descriptive name

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate well-formedness of the DFA definition."""
        if self.start_state not in self.states:
            raise ValueError(f"Start state '{self.start_state}' is not in states set.")
        if not self.accepting_states.issubset(self.states):
            missing = self.accepting_states - self.states
            raise ValueError(f"Accepting states {missing} are not in states set.")
        for (q, sym), target in self.delta.items():
            if q not in self.states:
                raise ValueError(f"Transition from unknown state '{q}'.")
            if sym not in self.alphabet:
                raise ValueError(f"Transition on unknown alphabet symbol '{sym}'.")
            if target not in self.states:
                raise ValueError(f"Transition targets unknown state '{target}'.")

    def step(self, state: str, symbol: str) -> str:
        """Execute one transition from state on symbol. Defaults to dead_state if undefined."""
        return self.delta.get((state, symbol), self.dead_state)

    def accepts(self, sequence: Sequence[str]) -> bool:
        """Test whether an event sequence is accepted by the DFA."""
        curr = self.start_state
        for sym in sequence:
            if sym not in self.alphabet:
                return False
            curr = self.step(curr, sym)
            if curr == self.dead_state:
                return False
        return curr in self.accepting_states

    def allowed_events(self, state: str) -> List[str]:
        """Return sorted list of alphabet symbols that do not lead to the dead state."""
        return sorted([sym for sym in self.alphabet if self.step(state, sym) != self.dead_state])

    def complete(self) -> "DFA":
        """Return a complete DFA where every state has an explicit transition on every symbol in alphabet."""
        new_states = set(self.states)
        new_states.add(self.dead_state)
        new_delta = dict(self.delta)

        for q in new_states:
            for sym in self.alphabet:
                if (q, sym) not in new_delta:
                    new_delta[(q, sym)] = self.dead_state

        new_names = dict(self.state_names)
        if self.dead_state not in new_names:
            new_names[self.dead_state] = "Dead"

        return DFA(
            states=new_states,
            alphabet=set(self.alphabet),
            delta=new_delta,
            start_state=self.start_state,
            accepting_states=set(self.accepting_states),
            dead_state=self.dead_state,
            state_names=new_names,
        )

    def is_complete(self) -> bool:
        """Check if delta has a total transition function Q x Sigma -> Q."""
        if self.dead_state not in self.states:
            return False
        for q in self.states:
            for sym in self.alphabet:
                if (q, sym) not in self.delta:
                    return False
        return True
