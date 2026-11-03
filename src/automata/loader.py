"""Workflow YAML specification loader and validator."""

from pathlib import Path
from typing import Dict, Set, Tuple

import yaml

from src.automata.dfa import DFA


def load_workflow(path: str | Path) -> DFA:
    """Load workflow YAML, perform specification linting, and return a complete DFA."""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Workflow specification file not found: {file_path}")

    with open(file_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError("Invalid YAML: Root must be a dictionary.")

    # 1. Parse alphabet
    alphabet_entries = data.get("alphabet", [])
    if not alphabet_entries:
        raise ValueError("Workflow specification must define a non-empty alphabet.")

    alphabet: Set[str] = set()
    code_to_name: Dict[str, str] = {}
    for entry in alphabet_entries:
        name = entry.get("name")
        code = entry.get("code")
        if not name:
            raise ValueError(f"Alphabet entry missing required 'name': {entry}")
        alphabet.add(name)
        if code:
            code_to_name[code] = name

    # 2. Parse states
    state_entries = data.get("states", [])
    if not state_entries:
        raise ValueError("Workflow specification must define at least one state.")

    states: Set[str] = set()
    state_names: Dict[str, str] = {}
    accepting_states: Set[str] = set()
    initial_states: Set[str] = set()
    dead_state: str = "S_dead"

    for state in state_entries:
        sid = state.get("id")
        if not sid:
            raise ValueError(f"State entry missing required 'id': {state}")
        if sid in states:
            raise ValueError(f"Duplicate state id '{sid}' found in specification.")

        states.add(sid)
        state_names[sid] = state.get("name", sid)

        if state.get("initial", False):
            initial_states.add(sid)
        if state.get("accepting", False):
            accepting_states.add(sid)
        if state.get("dead", False):
            dead_state = sid

    if len(initial_states) != 1:
        raise ValueError(f"Workflow must have exactly one initial state, found: {initial_states}")
    start_state = next(iter(initial_states))

    if not accepting_states:
        raise ValueError("Workflow specification must contain at least one accepting state.")

    # 3. Parse transitions
    transitions = data.get("transitions", [])
    delta: Dict[Tuple[str, str], str] = {}

    for t in transitions:
        src = t.get("from")
        event = t.get("event")
        dst = t.get("to")

        if not src or not event or not dst:
            raise ValueError(f"Incomplete transition definition: {t}")

        # Resolve code if code was used instead of full name
        event_name = code_to_name.get(event, event)

        if src not in states:
            raise ValueError(f"Transition references unknown source state '{src}'.")
        if dst not in states:
            raise ValueError(f"Transition references unknown destination state '{dst}'.")
        if event_name not in alphabet:
            raise ValueError(f"Transition references unknown alphabet event '{event}'.")

        key = (src, event_name)
        if key in delta and delta[key] != dst:
            raise ValueError(
                f"Non-deterministic transition conflict for state '{src}' on event '{event_name}': "
                f"targets both '{delta[key]}' and '{dst}'."
            )
        delta[key] = dst

    # 4. Build and complete the DFA
    dfa = DFA(
        states=states,
        alphabet=alphabet,
        delta=delta,
        start_state=start_state,
        accepting_states=accepting_states,
        dead_state=dead_state,
        state_names=state_names,
    )

    return dfa.complete()
