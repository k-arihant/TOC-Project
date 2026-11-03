from pathlib import Path

import yaml

from src.automata.dfa import DFA

DEFAULT_TCP_FSM_PATH = Path(__file__).resolve().parent / "tcp_fsm.yaml"


def load_tcp_dfa(
    profile: str = "strict",
    spec_path: str | Path | None = None,
) -> DFA:
    """
    Load a simplified TCP connection lifecycle DFA from YAML specification.

    Reuses the core automata.dfa.DFA class per Doc 07 §4.

    Args:
        profile: Tolerance profile: 'strict' or 'tolerant'.
        spec_path: Optional path to tcp_fsm.yaml file.

    Returns:
        DFA: Complete formal DFA for the specified TCP profile.
    """
    path = Path(spec_path) if spec_path else DEFAULT_TCP_FSM_PATH
    if not path.exists():
        raise FileNotFoundError(f"TCP FSM specification not found at: {path}")

    with open(path, encoding="utf-8") as f:
        spec = yaml.safe_load(f)

    alphabet: set[str] = set(spec.get("alphabet", []))
    states_data = spec.get("states", [])

    all_states: set[str] = set()
    initial_state: str = "T0"
    accepting_states: set[str] = set()
    dead_state = "T_dead"

    for s in states_data:
        sid = str(s["id"])
        all_states.add(sid)
        if s.get("initial", False):
            initial_state = sid
        if s.get("accepting", False):
            accepting_states.add(sid)

    # Load transitions for the selected profile
    profiles = spec.get("profiles", {})
    if profile not in profiles:
        raise ValueError(f"Unknown TCP profile '{profile}'. Must be 'strict' or 'tolerant'.")

    profile_transitions = profiles[profile].get("transitions", [])
    delta: dict[tuple[str, str], str] = {}

    for t in profile_transitions:
        src = str(t["from"])
        dst = str(t["to"])
        evt = str(t["event"])
        delta[(src, evt)] = dst

    # Complete the DFA: unlisted transitions from any state go to dead_state
    for s in all_states:
        for symbol in alphabet:
            if (s, symbol) not in delta:
                delta[(s, symbol)] = dead_state

    return DFA(
        states=all_states,
        alphabet=alphabet,
        delta=delta,
        start_state=initial_state,
        accepting_states=accepting_states,
        dead_state=dead_state,
    )
