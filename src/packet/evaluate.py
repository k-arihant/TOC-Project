import uuid
from collections import Counter
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

from src.automata.validator import validate_trace
from src.common.types import FsmVerdict
from src.packet.flows import Flow, build_flows
from src.packet.mapper import to_events
from src.packet.reader import read_packets
from src.packet.tcp_fsm import load_tcp_dfa

INTENDED_SCENARIO_VERDICTS: dict[str, str] = {
    "S1": "ACCEPTED_CLEAN",
    "S2": "ACCEPTED_RESET",
    "S3": "ACCEPTED_RESET",
    "S4": "INCOMPLETE",
    "S5": "INVALID",
}


def evaluate_flow_records(
    flows: Iterable[Flow],
    profile: str = "strict",
    scenario_map: dict[str, str] | None = None,
) -> dict:
    """
    Evaluate reconstructed TCP flows against the TCP DFA.

    Args:
        flows: Iterable of Flow objects.
        profile: 'strict' or 'tolerant'.
        scenario_map: Optional map from flow_id (or endpoint) to scenario ('S1'..'S5').

    Returns:
        dict: Experiment report matching Doc 07 §8 schema.
    """
    dfa = load_tcp_dfa(profile=profile)
    flow_list = list(flows)

    flow_results: list[dict] = []
    verdict_counts: Counter[str] = Counter()
    midstream_count = 0
    scenario_agreement: dict[str, dict[str, int]] = {}

    for flow in flow_list:
        scenario = None
        if scenario_map:
            scenario = scenario_map.get(flow.flow_id) or scenario_map.get(
                f"{flow.src_endpoint[0]}:{flow.src_endpoint[1]}"
            )
        flow_events = to_events(flow)

        if flow.is_midstream:
            verdict = "MIDSTREAM"
            fail_idx = None
            fail_state = None
            fail_event = None
            midstream_count += 1
        else:
            fsm_res = validate_trace(dfa, flow.flow_id, flow_events)
            if fsm_res.verdict == FsmVerdict.VALID_COMPLETE:
                last_state = fsm_res.state_path[-1]
                if last_state == "T6":
                    verdict = "ACCEPTED_CLEAN"
                elif last_state == "T7":
                    verdict = "ACCEPTED_RESET"
                else:
                    verdict = "ACCEPTED_CLEAN"
            elif fsm_res.verdict == FsmVerdict.VALID_PREFIX:
                verdict = "INCOMPLETE"
            else:  # INVALID
                verdict = "INVALID"

            fail_idx = fsm_res.fail_index
            fail_state = fsm_res.fail_state
            fail_event = fsm_res.fail_event

        verdict_counts[verdict] += 1

        # Check scenario agreement
        if scenario:
            if scenario not in scenario_agreement:
                scenario_agreement[scenario] = {"total": 0, "agreed": 0}
            scenario_agreement[scenario]["total"] += 1
            intended = INTENDED_SCENARIO_VERDICTS.get(scenario)
            if intended == verdict:
                scenario_agreement[scenario]["agreed"] += 1

        flow_results.append(
            {
                "flow_id": flow.flow_id,
                "src": f"{flow.src_endpoint[0]}:{flow.src_endpoint[1]}",
                "dst": f"{flow.dst_endpoint[0]}:{flow.dst_endpoint[1]}",
                "n_events": len(flow_events),
                "events": flow_events,
                "verdict": verdict,
                "fail_index": fail_idx,
                "fail_state": fail_state,
                "fail_event": fail_event,
                "scenario": scenario,
            }
        )

    exp_id = f"exp_tcp_{profile}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

    return {
        "experiment_id": exp_id,
        "profile": profile,
        "flows": flow_results,
        "summary": {
            "total_flows": len(flow_list),
            "midstream_excluded": midstream_count,
            "fsm_evaluated_flows": len(flow_list) - midstream_count,
            "counts_by_verdict": dict(verdict_counts),
            "scenario_agreement": scenario_agreement,
        },
    }


def run_experiment(
    pcap_path: str | Path,
    profile: str = "strict",
    scenario_map: dict[str, str] | None = None,
    max_packets: int = 10000,
) -> dict:
    """
    Run full streaming packet validation experiment on a PCAP file per Doc 07 §8 / Doc 14 §7.

    Args:
        pcap_path: Path to .pcap capture file.
        profile: 'strict' or 'tolerant'.
        scenario_map: Optional mapping for scenario identification.
        max_packets: Max packets to inspect.

    Returns:
        dict: Experiment report JSON.
    """
    records = list(read_packets(pcap_path, max_packets=max_packets))
    flows = build_flows(records)
    return evaluate_flow_records(flows, profile=profile, scenario_map=scenario_map)
