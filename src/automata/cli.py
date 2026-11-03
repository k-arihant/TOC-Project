"""Command-line interface for automata inspection and verification."""

import argparse
from pathlib import Path

from src.automata.equivalence import equivalent
from src.automata.explain import explain_fsm
from src.automata.loader import load_workflow
from src.automata.minimization import minimise
from src.automata.reachability import analyse
from src.automata.validator import validate_trace
from src.automata.variants import bounded_retry_dfa

DEFAULT_SPEC = Path("workflows/order_payment/workflow.yaml")


def cmd_validate(args: argparse.Namespace) -> None:
    dfa = load_workflow(args.spec)
    events = [e.strip() for e in args.trace.split(",") if e.strip()]
    result = validate_trace(dfa, case_id=args.case_id, activities=events)

    print(f"Case ID: {result.case_id}")
    print(f"Verdict: {result.verdict.value}")
    print(f"State Path: {' -> '.join(result.state_path)}")
    if result.reason_code:
        print(f"Reason Code: {result.reason_code}")
        print(f"Failing Position: {result.fail_index}")
        print(f"Offending Event: {result.fail_event}")
        print(f"Offending State: {result.fail_state}")
        print(
            f"Allowed Events: {', '.join(result.allowed_events) if result.allowed_events else 'None'}"
        )

    explanations = explain_fsm(result, dfa.state_names)
    print("\nExplanation:")
    for line in explanations:
        print(f"  • {line}")


def cmd_minimise(args: argparse.Namespace) -> None:
    dfa = load_workflow(args.spec)
    min_dfa, merged = minimise(dfa)

    print(f"Original DFA States: {len(dfa.states)}")
    print(f"Minimal DFA States: {len(min_dfa.states)}")
    print(f"State Reduction: {len(dfa.states) - len(min_dfa.states)} states eliminated.")
    print("\nMerged State Partitions:")
    for rep, members in sorted(merged.items()):
        if len(members) > 1:
            print(f"  • Representative '{rep}' merged original states: {members}")


def cmd_reachability(args: argparse.Namespace) -> None:
    dfa = load_workflow(args.spec)
    report = analyse(dfa)

    print(f"Total States: {len(dfa.states)}")
    print(f"Reachable States ({len(report.reachable)}): {sorted(report.reachable)}")
    print(
        f"Unreachable States ({len(report.unreachable)}): {sorted(report.unreachable) if report.unreachable else 'None'}"
    )
    print(f"Dead States ({len(report.dead)}): {sorted(report.dead)}")
    print(f"Useful States ({len(report.useful)}): {len(report.useful)} states")


def cmd_equiv(args: argparse.Namespace) -> None:
    dfa1 = load_workflow(args.spec)
    if args.compare_with == "minimised":
        dfa2, _ = minimise(dfa1)
        name2 = "Minimised DFA"
    elif args.compare_with.startswith("bounded_"):
        k = int(args.compare_with.split("_")[1])
        dfa2 = bounded_retry_dfa(k)
        name2 = f"Bounded DFA (k={k})"
    else:
        dfa2 = load_workflow(args.compare_with)
        name2 = args.compare_with

    is_eq, counter = equivalent(dfa1, dfa2)
    if is_eq:
        print(f"Result: The two DFAs are LANGUAGE-EQUIVALENT: L(D1) == L({name2}).")
    else:
        print("Result: The two DFAs are NOT equivalent.")
        print(f"Counter-example witness string: {counter}")


def main() -> None:
    parser = argparse.ArgumentParser(description="TOC Automata Engine CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Validate
    p_val = subparsers.add_parser("validate", help="Validate an event trace")
    p_val.add_argument("--spec", default=DEFAULT_SPEC, help="Path to workflow YAML")
    p_val.add_argument("--trace", required=True, help="Comma-separated event names or codes")
    p_val.add_argument("--case-id", default="adhoc-1", help="Case identifier")
    p_val.set_defaults(func=cmd_validate)

    # Minimise
    p_min = subparsers.add_parser("minimise", help="Minimise workflow DFA using Moore's algorithm")
    p_min.add_argument("--spec", default=DEFAULT_SPEC, help="Path to workflow YAML")
    p_min.set_defaults(func=cmd_minimise)

    # Reachability
    p_reach = subparsers.add_parser(
        "reach", help="Compute reachability, co-reachability, and dead states"
    )
    p_reach.add_argument("--spec", default=DEFAULT_SPEC, help="Path to workflow YAML")
    p_reach.set_defaults(func=cmd_reachability)

    # Equivalence
    p_eq = subparsers.add_parser("equiv", help="Check language equivalence between DFAs")
    p_eq.add_argument("--spec", default=DEFAULT_SPEC, help="Path to first workflow YAML")
    p_eq.add_argument(
        "--compare-with",
        default="minimised",
        help="Comparison target: 'minimised', 'bounded_<k>', or path to second YAML",
    )
    p_eq.set_defaults(func=cmd_equiv)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
