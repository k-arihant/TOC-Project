"""Page 1 — Automata Explorer (Formal Theory of Computation Domain).

Adheres strictly to Doc 09 §1 & Doc 04.
Pure API client: all DFA, NFA, minimization, and validation data is fetched from the REST API.
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
from src.dashboard.components.graphs import render_automaton
from src.dashboard.components.provenance import render_provenance_footer

api: ApiClient = st.session_state.get("api_client", ApiClient())

st.title("🏛️ Automata Explorer")
st.subheader("Formal Language Specification, State Minimisation & Trace Stepping")

tab_inspector, tab_dfa, tab_nfa, tab_min, tab_reach, tab_equiv = st.tabs(
    [
        "🔍 Trace Inspector",
        "🌐 Base Complete DFA",
        "🔀 Thompson NFA → DFA",
        "📉 Moore Minimisation",
        "🎯 State Reachability",
        "⚖️ Language Equivalence",
    ]
)

# Fetch Base DFA from API
wf_id = 1
dfa_data = None
try:
    dfa_data = api.get_workflow_automaton(workflow_id=wf_id, kind="DFA")
except Exception as exc:
    st.error(f"Could not load Base DFA from API: {exc}")


# =========================================================================
# TAB 1: TRACE INSPECTOR (The central visual interactive requirement)
# =========================================================================
with tab_inspector:
    st.markdown("### Interactive Trace Inspector & Graph Stepper")
    st.write(
        "Input or select an execution trace. The validator analyzes the trace in linear time $O(n)$, "
        "detects any formal grammar violations, lists permitted next events, and renders the path directly on the DFA "
        "highlighting valid steps in **bold blue** and any illegal transition in **bright red**."
    )

    preset_traces = {
        "Valid Complete: Happy Path": [
            "OrderCreated",
            "PaymentInitiated",
            "PaymentAuthorized",
            "OrderPacked",
            "OrderShipped",
            "OrderDelivered",
            "OrderClosed",
        ],
        "Valid Complete: Payment Retry Success": [
            "OrderCreated",
            "PaymentInitiated",
            "PaymentFailed",
            "PaymentInitiated",
            "PaymentAuthorized",
            "OrderPacked",
            "OrderShipped",
            "OrderDelivered",
            "OrderClosed",
        ],
        "Valid Complete: Return & Refund": [
            "OrderCreated",
            "PaymentInitiated",
            "PaymentAuthorized",
            "OrderPacked",
            "OrderShipped",
            "OrderDelivered",
            "RefundRequested",
            "RefundCompleted",
            "OrderClosed",
        ],
        "Valid Prefix: Order In Progress (Not Yet Closed)": [
            "OrderCreated",
            "PaymentInitiated",
            "PaymentAuthorized",
            "OrderPacked",
        ],
        "RULE VIOLATION: Premature Shipping (Skipped Payment)": [
            "OrderCreated",
            "OrderShipped",
        ],
        "RULE VIOLATION: Activity After Terminal Closed State": [
            "OrderCreated",
            "PaymentInitiated",
            "PaymentAuthorized",
            "OrderPacked",
            "OrderShipped",
            "OrderDelivered",
            "OrderClosed",
            "OrderPacked",
        ],
        "RULE VIOLATION: Double Payment Authorization": [
            "OrderCreated",
            "PaymentInitiated",
            "PaymentAuthorized",
            "PaymentAuthorized",
        ],
    }

    selected_preset = st.selectbox("Choose a pre-configured scenario:", list(preset_traces.keys()))
    default_events = "\n".join(preset_traces[selected_preset])

    trace_text = st.text_area(
        "Trace Activities (one per line):",
        value=default_events,
        height=180,
    )

    activities = [line.strip() for line in trace_text.strip().splitlines() if line.strip()]

    if st.button("🚀 Validate Trace", type="primary", use_container_width=True):
        if not activities:
            st.warning("Please provide at least one activity event.")
        else:
            try:
                result = api.validate_trace(
                    workflow_id=wf_id,
                    case_id="manual-inspector",
                    activities=activities,
                )

                verdict = result.get("verdict")
                state_path = result.get("state_path", [])
                fail_idx = result.get("fail_index")
                fail_state = result.get("fail_state")
                fail_event = result.get("fail_event")
                allowed_events = result.get("allowed_events", [])
                explanations = result.get("explanation", [])

                # Verdict Banner
                col_v1, col_v2, col_v3 = st.columns(3)
                with col_v1:
                    if verdict == "VALID_COMPLETE":
                        st.success(f"### Verdict: {verdict}")
                    elif verdict == "VALID_PREFIX":
                        st.warning(f"### Verdict: {verdict}")
                    else:
                        st.error(f"### Verdict: {verdict}")

                with col_v2:
                    st.metric("Total Events", len(activities))
                with col_v3:
                    st.metric("Final State Reached", state_path[-1] if state_path else "S0")

                # Explanations Card
                st.markdown("#### 📝 Diagnostic Explanations")
                for exp in explanations:
                    if verdict == "INVALID":
                        st.error(f"• {exp}")
                    elif verdict == "VALID_PREFIX":
                        st.warning(f"• {exp}")
                    else:
                        st.success(f"• {exp}")

                if verdict == "INVALID" and allowed_events:
                    st.info(f"**Permitted Events from state '{fail_state}':** `{'`, `'.join(allowed_events)}`")

                # Execution Stepper Table
                st.markdown("#### 👣 Step-by-Step State Traversal")
                steps_data = []
                for i, act in enumerate(activities):
                    curr_st = state_path[i] if i < len(state_path) else "Unknown"
                    next_st = state_path[i + 1] if (i + 1) < len(state_path) else "S_dead"
                    is_failed = (i == fail_idx)
                    status_str = "❌ ILLEGAL TRANSITION" if is_failed else "✅ OK"
                    steps_data.append(
                        {
                            "Step": i + 1,
                            "From State": curr_st,
                            "Event Received": act,
                            "To State": next_st,
                            "Status": status_str,
                        }
                    )
                st.dataframe(pd.DataFrame(steps_data), use_container_width=True)

                # Highlighted Automaton Diagram
                st.markdown("#### 🗺️ Path Visualisation Over Complete DFA")
                st.caption(
                    "Blue edges represent the traversed path. A bright red edge indicates the exact invalid transition."
                )
                if dfa_data and "dot" in dfa_data:
                    render_automaton(
                        dot_text=dfa_data["dot"],
                        visited_states=state_path,
                        failing_state=fail_state if verdict == "INVALID" else None,
                        failing_event=fail_event if verdict == "INVALID" else None,
                        fail_from_state=fail_state if verdict == "INVALID" else None,
                    )

            except ApiClientError as err:
                st.error(f"Validation failed: {err}")


# =========================================================================
# TAB 2: BASE COMPLETE DFA
# =========================================================================
with tab_dfa:
    st.markdown("### Base Complete DFA (13 Live States + Explicit $S_{\\text{dead}}$)")
    st.write(
        "Formal complete DFA specification for the online order & payment lifecycle. "
        "Contains 14 states and 154 total transitions (11 alphabet symbols $\\times$ 14 states). "
        "Every unlisted transition explicitly transitions to the absorbing dead state $S_{\\text{dead}}$."
    )

    if dfa_data:
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.metric("Total States", len(dfa_data.get("states", [])))
        with col_m2:
            st.metric("Accepting States", len(dfa_data.get("accepting_states", [])))
        with col_m3:
            st.metric("Total Defined Transitions", len(dfa_data.get("transitions", [])))

        st.markdown("#### State Definitions")
        df_states = pd.DataFrame(dfa_data.get("states", []))
        st.dataframe(df_states, use_container_width=True)

        st.markdown("#### Complete Transition Table (Sample)")
        df_trans = pd.DataFrame(dfa_data.get("transitions", []))
        st.dataframe(df_trans.head(30), use_container_width=True)

        st.markdown("#### Visual State Diagram")
        render_automaton(dot_text=dfa_data.get("dot", ""))


# =========================================================================
# TAB 3: THOMPSON NFA → DFA (Subset Construction)
# =========================================================================
with tab_nfa:
    st.markdown("### Subset Construction: Thompson NFA to Deterministic DFA")
    st.write(
        "Demonstrates the classical power-set construction algorithm transforming an NFA with non-deterministic "
        "payment retry branches into an equivalent DFA without $\\varepsilon$-transitions."
    )

    if st.button("🔄 Run Subset Construction Algorithm", type="primary"):
        try:
            nfa_resp = api.nfa_to_dfa(use_default_retry=True)
            step_table = nfa_resp.get("step_table", [])
            dfa_states = nfa_resp.get("states", [])
            accepting_states = nfa_resp.get("accepting_states", [])

            st.success(f"Subset Construction Succeeded! Constructed {len(dfa_states)} DFA states.")

            col_n1, col_n2 = st.columns(2)
            with col_n1:
                st.markdown("#### Subset Construction Step Table")
                st.caption("Maps each newly formed DFA state to the corresponding subset of NFA states.")
                st.dataframe(pd.DataFrame(step_table), use_container_width=True)

            with col_n2:
                st.markdown("#### Converted DFA Transitions")
                st.caption(f"Start State: `{nfa_resp.get('start_state')}` | Accepting States: `{accepting_states}`")
                df_nfa_trans = pd.DataFrame(nfa_resp.get("transitions", []))
                st.dataframe(df_nfa_trans, use_container_width=True)

        except ApiClientError as err:
            st.error(f"Subset construction failed: {err}")


# =========================================================================
# TAB 4: MOORE STATE MINIMISATION
# =========================================================================
with tab_min:
    st.markdown("### Moore's Partition Refinement Minimisation")
    st.write(
        "Minimises the base 14-state complete DFA by iteratively partitioning states into 1-distinguishable equivalence classes. "
        "Per hand-derived proof in Doc 04 §6, states `{S1 (Created), S3 (PaymentFailed)}` and `{S8 (CancelledUnpaid), S11 (Refunded)}` "
        "exhibit identical future behaviour and are merged, yielding an exact **12-state canonical minimal DFA**."
    )

    if st.button("📉 Execute Moore Minimisation", type="primary"):
        try:
            min_resp = api.minimize_dfa(workflow_id=wf_id)
            states = min_resp.get("states", [])
            partition = min_resp.get("merged_partition", {})
            trans = min_resp.get("transitions", [])

            st.success(f"DFA minimised from 14 states to {len(states)} states!")

            col_p1, col_p2 = st.columns(2)
            with col_p1:
                st.markdown("#### Merged Equivalence Partitions")
                st.caption("Shows which states in the unminimised DFA collapsed into single minimal states.")
                part_rows = [{"Minimal State": k, "Original States Merged": ", ".join(v)} for k, v in partition.items()]
                st.dataframe(pd.DataFrame(part_rows), use_container_width=True)

            with col_p2:
                st.markdown("#### Minimal DFA Transitions")
                st.dataframe(pd.DataFrame(trans).head(25), use_container_width=True)

        except ApiClientError as err:
            st.error(f"Minimisation failed: {err}")


# =========================================================================
# TAB 5: REACHABILITY & TRAP STATE ANALYSIS
# =========================================================================
with tab_reach:
    st.markdown("### State Reachability & Dead State Analysis")
    st.write(
        "Evaluates the topology of the DFA using forward BFS from the initial state $S_0$ and backward BFS from accepting states $F$."
    )

    if st.button("🔍 Analyze Reachability"):
        try:
            # Automaton ID 1 is base DFA
            reach_data = api.get_reachability(automaton_id=1)
            reachable = reach_data.get("reachable_states", [])
            unreachable = reach_data.get("unreachable_states", [])
            dead = reach_data.get("dead_states", [])
            useful = reach_data.get("useful_states", [])

            col_r1, col_r2, col_r3, col_r4 = st.columns(4)
            col_r1.metric("Reachable States", len(reachable))
            col_r2.metric("Unreachable States", len(unreachable))
            col_r3.metric("Trap/Dead States", len(dead))
            col_r4.metric("Useful States", len(useful))

            st.markdown(f"**Reachable States ($S_0 \\to^* q$):** `{', '.join(sorted(reachable))}`")
            st.markdown(f"**Unreachable States:** `{', '.join(sorted(unreachable)) if unreachable else 'None (0 states)'}`")
            st.markdown(f"**Dead/Absorbing States ($q \\not\\to^* F$):** `{', '.join(sorted(dead))}`")
            st.markdown(f"**Useful States:** `{', '.join(sorted(useful))}`")

            st.info(
                "💡 **TOC Theoretical Note:** A trap state is defined as an absorbing non-accepting state $\\delta(S_{\\text{dead}}, \\sigma) = S_{\\text{dead}}$ "
                "from which no accepting state is reachable. Its presence guarantees that the transition function $\\delta: Q \\times \\Sigma \\to Q$ is total."
            )
        except ApiClientError as err:
            st.error(f"Reachability check failed: {err}")


# =========================================================================
# TAB 6: LANGUAGE EQUIVALENCE
# =========================================================================
with tab_equiv:
    st.markdown("### Formal Language Equivalence Verification ($L(M_1) \\equiv L(M_2)$)")
    st.write(
        "Tests whether two automata accept the exact same regular language using a product automaton BFS searching for "
        "a symmetric difference state $(q_1, q_2)$ where $(q_1 \\in F_1 \\land q_2 \\notin F_2) \\lor (q_1 \\notin F_1 \\land q_2 \\in F_2)$."
    )

    st.markdown("Testing Equivalence between **Base Complete DFA** and **Moore Minimized DFA**:")

    if st.button("⚖️ Verify Language Equivalence", type="primary"):
        try:
            # In test/seed DB: Automaton ID 1 is Base DFA, Automaton ID 2 is Minimized DFA
            eq_res = api.check_equivalence(automaton_id_1=1, automaton_id_2=2)
            is_eq = eq_res.get("equivalent")
            counterex = eq_res.get("counterexample")

            if is_eq:
                st.success("🎉 **PROVEN EQUIVALENT:** $L(\\text{Base DFA}) = L(\\text{Moore Minimized DFA})$")
                st.info(
                    "The product automaton BFS search terminated having verified that all reachable state pairs share identical "
                    "acceptance status. Counterexample: `None`."
                )
            else:
                st.error("❌ **NOT EQUIVALENT:** Found counterexample trace!")
                st.code(f"Distinguishing string: {counterex}")

        except ApiClientError as err:
            st.error(f"Equivalence verification failed: {err}")

render_provenance_footer(st.session_state.get("current_dataset_info"))
