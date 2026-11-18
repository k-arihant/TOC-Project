"""Page 5 — Supplementary Packet Validation (Network Protocol Automata Domain).

Adheres strictly to Doc 09 §1 & Doc 07.
Pure API client: demonstrates automata validation on simplified TCP network flows.
Clearly marked as a supplementary 10-15% academic experiment (NOT an IDS).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure repository root is on sys.path
for _p in Path(__file__).resolve().parents:
    if (_p / "src").is_dir():
        if str(_p) not in sys.path:
            sys.path.insert(0, str(_p))
        break

import pandas as pd
import streamlit as st

from src.dashboard.api_client import ApiClient, ApiClientError
from src.dashboard.components.provenance import render_provenance_footer

api: ApiClient = st.session_state.get("api_client", ApiClient())

st.title("Supplementary Packet Validation")
st.subheader("Simplified TCP Connection State Machine Verification")

# Prominent Scope & Limitations Banner per Doc 09 §1 & Doc 07
st.warning(
    "**Academic Scope Disclaimer:** This is an independent, supplementary experiment (capped at 10–15% of project effort). "
    "It demonstrates formal automata validation on network connection handshakes and teardowns. "
    "**It is NOT an Intrusion Detection System (IDS):** FSM-invalid $\\neq$ malicious attack, and FSM-valid $\\neq$ benign traffic."
)

tab_upload, tab_experiments, tab_flows = st.tabs(
    [
        "Upload & Run PCAP Experiment",
        "Experiment Runs & Agreement",
        "Flow Drill-Down & TCP FSM Paths",
    ]
)

# =========================================================================
# TAB 1: UPLOAD & RUN PCAP EXPERIMENT
# =========================================================================
with tab_upload:
    st.markdown("### Upload PCAP Capture")
    st.write(
        "Upload a packet capture file (PCAP) to slice bidirectional 5-tuple TCP streams and validate "
        "packet sequences against the formal TCP finite state machine."
    )

    with st.form("pcap_upload_form"):
        exp_name = st.text_input("Experiment Name", value="Lab_Capture_Experiment_v1")
        source_desc = st.text_input("Source Description", value="Authorized lab testbed TCP traffic capture")
        profile = st.selectbox(
            "Select TCP Automaton Profile:",
            [
                ("strict", "Strict FSM (Enforces exact SYN -> SYN-ACK -> ACK and FIN handshakes)"),
                ("tolerant", "Tolerant FSM (Permits TCP RST resets, keep-alives, and out-of-order teardowns)"),
            ],
            format_func=lambda x: x[1],
        )[0]
        notes = st.text_area("Experiment Notes", value="Evaluating protocol handshake conformance on TCP sessions.")
        pcap_file = st.file_uploader("Upload PCAP File (`.pcap`, max 25MB)", type=["pcap", "pcapng"])

        submit_pcap = st.form_submit_button("Process PCAP & Run FSM Validation", type="primary", width="stretch")
        if submit_pcap:
            if not pcap_file:
                st.warning("Please upload a PCAP file.")
            else:
                with st.spinner("Streaming packets with scapy, slicing 5-tuple flows, and validating FSM transitions..."):
                    try:
                        res = api.upload_packet_experiment(
                            name=exp_name,
                            source_description=source_desc,
                            profile=profile,
                            pcap_bytes=pcap_file.getvalue(),
                            notes=notes,
                            filename=pcap_file.name,
                        )
                        st.success(f"Processed Experiment #{res.get('experiment_id')}: Found {res.get('n_flows', 0)} TCP flows!")
                        st.session_state.current_pcap_exp_id = res.get("experiment_id")
                        st.rerun()
                    except ApiClientError as err:
                        st.error(f"Experiment processing failed: {err}")


# =========================================================================
# TAB 2: EXPERIMENT RUNS & SCENARIO AGREEMENT
# =========================================================================
with tab_experiments:
    st.markdown("### Stored Packet Experiments")
    try:
        exps = api.list_packet_experiments()
        if not exps:
            st.info("No PCAP experiments recorded yet. Upload a PCAP file in the **Upload & Run PCAP Experiment** tab.")
        else:
            df_exp = pd.DataFrame(exps)
            st.dataframe(df_exp, width="stretch")

            selected_eid = st.selectbox(
                "Select Experiment to View Details:",
                options=[e["experiment_id"] for e in exps],
                format_func=lambda eid: next((f"#{eid}: {e['name']} ({e['profile']} profile)" for e in exps if e["experiment_id"] == eid), str(eid)),
            )

            if selected_eid:
                e_detail = api.get_packet_experiment(selected_eid)
                st.session_state.current_pcap_exp_id = selected_eid

                raw_flows = api.get_packet_experiment_flows(selected_eid)
                flow_items = [fl.get("flow", fl) for fl in raw_flows]
                total_flows = len(flow_items) if flow_items else e_detail.get("flow_count", 0)
                valid_flows = sum(1 for fl in flow_items if fl.get("verdict") == "VALID")
                invalid_flows = total_flows - valid_flows
                total_pkts = sum(fl.get("n_events", 0) for fl in flow_items)

                st.markdown(f"#### Experiment #{selected_eid} Summary Metrics")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Total Packets", total_pkts)
                c2.metric("Total Flows", total_flows)
                c3.metric("FSM Valid Flows", valid_flows)
                c4.metric("FSM Invalid Flows", invalid_flows)

                rate = (valid_flows / total_flows) if total_flows > 0 else 0.0
                st.progress(rate, text=f"Protocol Conformance Rate: {rate:.1%}")

                st.markdown("#### Formal Inclusion Theorem")
                st.info(
                    "**Language Hierarchy Proof:** $L(\\text{Strict}) \\subset L(\\text{Tolerant})$.\n"
                    "Because the Tolerant FSM is constructed by adding transition edges (e.g. for TCP RST flags, retransmissions, "
                    "and asynchronous FIN closes) to the Strict FSM without removing any existing transitions, "
                    "every packet trace accepted by the Strict FSM is necessarily accepted by the Tolerant FSM."
                )

    except Exception as exc:
        st.error(f"Could not load packet experiments: {exc}")


# =========================================================================
# TAB 3: FLOW DRILL-DOWN & TCP FSM PATHS
# =========================================================================
with tab_flows:
    st.markdown("### TCP 5-Tuple Flow Drill-Down")
    current_eid = st.session_state.get("current_pcap_exp_id")

    if not current_eid:
        st.info("Select or upload an experiment in the tabs above to inspect individual TCP flows.")
    else:
        st.markdown(f"**Viewing Flows for Experiment #{current_eid}**")
        try:
            raw_flows = api.get_packet_experiment_flows(current_eid)
            if not raw_flows:
                st.info("No flow records found for this experiment.")
            else:
                flow_items = []
                flow_map = {}
                for item in raw_flows:
                    fl = item.get("flow", item)
                    fid = fl.get("flow_id")
                    evs = item.get("events", [])
                    src_s = f"{fl.get('src_ip')}:{fl.get('src_port')}" if fl.get('src_ip') else "N/A"
                    dst_s = f"{fl.get('dst_ip')}:{fl.get('dst_port')}" if fl.get('dst_ip') else "N/A"
                    five_tuple = f"{src_s} -> {dst_s}"
                    fl_entry = {
                        "flow_id": fid,
                        "5-Tuple": five_tuple,
                        "Packets": fl.get("n_events", len(evs)),
                        "Verdict": fl.get("verdict"),
                        "Scenario": fl.get("scenario") or "Standard Flow",
                    }
                    flow_items.append(fl_entry)
                    flow_map[fid] = {"flow": fl, "events": evs, "five_tuple": five_tuple}

                st.dataframe(pd.DataFrame(flow_items), width="stretch")

                st.markdown("#### Flow Path Inspector")
                selected_fid = st.selectbox(
                    "Choose Flow ID to inspect state transitions:",
                    options=[f["flow_id"] for f in flow_items],
                    format_func=lambda fid: f"Flow #{fid} | {flow_map[fid]['five_tuple']} | Verdict: {flow_map[fid]['flow'].get('verdict')}",
                )

                if selected_fid:
                    selected_data = flow_map[selected_fid]
                    flow_obj = selected_data["flow"]
                    ev_list = selected_data["events"]

                    col_fl1, col_fl2 = st.columns(2)
                    with col_fl1:
                        st.markdown("**Flow Specifications:**")
                        st.write(f"• **5-Tuple:** `{selected_data['five_tuple']}`")
                        st.write(f"• **Packets:** {flow_obj.get('n_events', len(ev_list))}")
                        st.write(f"• **FSM Verdict:** `{flow_obj.get('verdict')}`")
                        st.write(f"• **Scenario:** `{flow_obj.get('scenario') or 'None'}`")

                    with col_fl2:
                        st.markdown("**Automata Path:**")
                        ev_symbols = [e.get("symbol") for e in ev_list] if ev_list else []
                        st.write(f"• **Event Symbols:** `{' -> '.join(ev_symbols) if ev_symbols else 'No events recorded'}`")
                        if flow_obj.get("verdict") == "INVALID":
                            st.error("TCP FSM transition violation encountered on flow stream.")
                        else:
                            st.success("TCP FSM conformance verified for flow stream.")

        except Exception as exc:
            st.error(f"Error loading flow details: {exc}")

st.divider()
st.markdown("### Known Limitations & Boundary Guard (Doc 07 §5)")
st.info(
    """
    1. **Not an Intrusion Detection System (IDS):** Network attacks often utilize RFC-compliant TCP handshakes. Conversely, benign packet loss, NAT retransmissions, or middlebox interference can produce out-of-order frames that violate strict FSM transitions.
    2. **Simplified Model:** Real-world TCP engines maintain sliding window buffers, sequence/acknowledgement numbers, and reassembly queues that require a Turing-equivalent or counter model beyond a finite state automaton.
    3. **Supplementary Status:** This module is strictly scoped at $10\\text{--}15\\%$ of effort to satisfy academic requirements without detracting from the primary business workflow pipeline.
    """
)

render_provenance_footer(st.session_state.get("current_dataset_info"))
