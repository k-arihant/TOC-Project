import argparse
import sys
from pathlib import Path

# Ensure repository root is on sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import yaml

from src.automata.loader import load_workflow
from src.automata.minimization import minimise
from src.automata.nfa import build_payment_block_nfa
from src.db.repositories.workflow_repo import WorkflowRepository
from src.db.session import SessionLocal, create_tables


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed the database with initial workflow and automata specifications."
    )
    parser.add_argument(
        "--spec",
        type=str,
        default="workflows/order_payment/workflow.yaml",
        help="Path to workflow YAML spec.",
    )
    return parser.parse_args()


def seed_database(spec_path: str = "workflows/order_payment/workflow.yaml") -> None:
    path = Path(spec_path)
    if not path.exists():
        raise FileNotFoundError(f"Workflow specification not found: {path}")

    # Ensure tables exist
    create_tables()

    db = SessionLocal()
    repo = WorkflowRepository(db)

    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        name = data.get("name", "Online Order & Payment Lifecycle")
        version = data.get("version", "1.0.0")
        desc = data.get("description", "").strip()

        # Check if already seeded
        existing_wf = repo.get_by_name_and_version(name, version)
        if existing_wf is not None:
            print(
                f"[Seed] Workflow '{name}' v{version} already exists in database (ID: {existing_wf.workflow_id}). Skipping seed."
            )
            return

        print(f"[Seed] Creating Workflow: '{name}' v{version}...")
        wf = repo.create_workflow(name=name, version=version, description=desc)

        # 1. Add Alphabet Events
        alphabet_data = data.get("alphabet", [])
        events_to_add = [(item["code"], item["name"]) for item in alphabet_data]
        repo.add_events(wf.workflow_id, events_to_add)
        print(f"[Seed] Added {len(events_to_add)} workflow alphabet events.")

        # Event name -> event_id lookup
        event_id_map: dict[str, int] = {}
        for _, ename in events_to_add:
            evt_obj = repo.get_event_by_name(wf.workflow_id, ename)
            if evt_obj:
                event_id_map[ename] = evt_obj.event_id

        # 2. Base Complete DFA
        print("[Seed] Loading base complete DFA...")
        dfa = load_workflow(str(path))

        states_list = []
        for s in dfa.states:
            states_list.append(
                {
                    "name": s,
                    "initial": (s == dfa.start_state),
                    "accepting": (s in dfa.accepting_states),
                    "dead": (s == dfa.dead_state),
                }
            )

        transitions_list = []
        for (q, sym), target in dfa.delta.items():
            transitions_list.append(
                {
                    "from": q,
                    "event_id": event_id_map.get(sym),
                    "to": target,
                }
            )

        dfa_auto = repo.create_automaton(
            workflow_id=wf.workflow_id,
            kind="DFA",
            label="Base Complete DFA",
            states=states_list,
            transitions=transitions_list,
        )
        print(
            f"[Seed] Base DFA seeded with {len(states_list)} states and {len(transitions_list)} transitions (ID: {dfa_auto.automaton_id})."
        )

        # 3. Moore Minimised DFA
        print("[Seed] Computing Moore minimised DFA...")
        min_dfa, partition = minimise(dfa)

        min_states_list = []
        for s in min_dfa.states:
            min_states_list.append(
                {
                    "name": s,
                    "initial": (s == min_dfa.start_state),
                    "accepting": (s in min_dfa.accepting_states),
                    "dead": (s == min_dfa.dead_state),
                    "merged_from": partition.get(s, [s]),
                }
            )

        min_transitions_list = []
        for (q, sym), target in min_dfa.delta.items():
            min_transitions_list.append(
                {
                    "from": q,
                    "event_id": event_id_map.get(sym),
                    "to": target,
                }
            )

        min_auto = repo.create_automaton(
            workflow_id=wf.workflow_id,
            kind="MIN_DFA",
            label="Moore Minimised DFA",
            states=min_states_list,
            transitions=min_transitions_list,
            derived_from=dfa_auto.automaton_id,
        )
        print(
            f"[Seed] Minimised DFA seeded with {len(min_states_list)} states and {len(min_transitions_list)} transitions (ID: {min_auto.automaton_id})."
        )

        # 4. Payment Retry NFA
        print("[Seed] Seeding Thompson payment retry NFA...")
        nfa = build_payment_block_nfa()

        nfa_states_list = []
        for s in nfa.states:
            nfa_states_list.append(
                {
                    "name": s,
                    "initial": (s == nfa.start_state),
                    "accepting": (s in nfa.accepting_states),
                    "dead": False,
                }
            )

        nfa_transitions_list = []
        for (q, sym), targets in nfa.delta.items():
            for target in targets:
                nfa_transitions_list.append(
                    {
                        "from": q,
                        "event_id": event_id_map.get(sym) if sym else None,
                        "to": target,
                    }
                )

        nfa_auto = repo.create_automaton(
            workflow_id=wf.workflow_id,
            kind="NFA",
            label="Thompson Payment Retry NFA",
            states=nfa_states_list,
            transitions=nfa_transitions_list,
            derived_from=dfa_auto.automaton_id,
        )
        print(
            f"[Seed] Payment Retry NFA seeded with {len(nfa_states_list)} states (ID: {nfa_auto.automaton_id})."
        )

        print(
            "\n[Seed] Database successfully seeded with all initial workflow and automata specifications!"
        )

    finally:
        db.close()


def main() -> None:
    args = parse_args()
    seed_database(args.spec)


if __name__ == "__main__":
    main()
