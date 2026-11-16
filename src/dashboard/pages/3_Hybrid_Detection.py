"""Page 4 — Hybrid Detection & Case Drill-down (Fusion & Decision Engine Domain).

Adheres strictly to Doc 09 §1 & Doc 05.
Pure API client: runs real-time ad-hoc trace analysis, batch dataset scoring, dual-source explanations, and downloadable reports.
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

# Auto-initialize dataset if not present in session state
if not st.session_state.get("current_dataset_id"):
    try:
        datasets = api.list_datasets()
        if datasets:
            st.session_state.current_dataset_id = datasets[-1]["dataset_id"]
            st.session_state.current_dataset_info = datasets[-1]
    except Exception:
        pass

st.title("🔀 Hybrid Decision Engine & Explanations")
st.subheader("Dual-Source Explainability Combining Formal DFA Violations with Statistical Feature Deviations")

tab_single, tab_batch = st.tabs(["🧪 Single Trace Live Tester", "📦 Batch Split Analysis & Drill-down"])

# =========================================================================
# TAB 1: SINGLE TRACE LIVE TESTER
# =========================================================================
with tab_single:
    st.markdown("### Real-Time Hybrid Decision & Explainability")
    st.write(
        "Submit an event sequence to be evaluated jointly by the deterministic DFA and active machine learning models. "
        "The hybrid engine outputs the definitive 4-row matrix verdict and synthesizes human-readable explanations."
    )

    preset_cases = {
        "Happy Path (Valid & Normal)": [
            "OrderCreated",
            "PaymentInitiated",
            "PaymentAuthorized",
            "OrderPacked",
            "OrderShipped",
            "OrderDelivered",
            "OrderClosed",
        ],
        "Syntax Violation: Jump to Delivered without Payment": [
            "OrderCreated",
            "OrderDelivered",
        ],
        "Statistical Timing Anomaly: Excessive Delay (Valid FSM)": [
            "OrderCreated",
            "PaymentInitiated",
            "PaymentAuthorized",
            "OrderPacked",
            "OrderShipped",
            "OrderDelivered",
            "OrderClosed",
        ],
        "Incomplete Prefix: Waiting for Delivery & Close": [
            "OrderCreated",
            "PaymentInitiated",
            "PaymentAuthorized",
            "OrderPacked",
            "OrderShipped",
        ],
    }

    choice = st.selectbox("Select sample trace or compose custom events:", list(preset_cases.keys()))
    events_input = st.text_area(
        "Trace Activities (one per line):",
        value="\n".join(preset_cases[choice]),
        height=180,
    )

    activities = [line.strip() for line in events_input.strip().splitlines() if line.strip()]

    cur_ds_id = st.session_state.get("current_dataset_id")
    available_models = []
    try:
        available_models = api.list_models(dataset_id=cur_ds_id) if cur_ds_id else api.list_models()
    except Exception:
        pass

    col_m1, col_m2 = st.columns(2)
    with col_m1:
        model_options = [m["model_run_id"] for m in available_models]
        active_mids = st.multiselect(
            "Select ML models to consult:",
            options=model_options,
            default=model_options if model_options else [1, 2, 3, 4],
            format_func=lambda mid: next((f"#{mid} ({m['detector'].replace('_', ' ').title()})" for m in available_models if m["model_run_id"] == mid), f"Model #{mid}"),
        )
    with col_m2:
        policy = st.selectbox("ML Voting Policy:", ["any", "majority", "unanimous"])

    if st.button("⚡ Evaluate Hybrid Decision", type="primary", width="stretch"):
        if not activities:
            st.warning("Provide at least one activity.")
        else:
            try:
                dec = api.detect_analyze(
                    workflow_id=1,
                    case_id="adhoc-hybrid",
                    activities=activities,
                    model_run_ids=active_mids,
                    ml_policy=policy,
                )

                final_label = dec.get("final_label")
                fsm = dec.get("fsm", {})
                ml_scores = dec.get("ml", []) or dec.get("ml_scores", [])
                explanations = dec.get("explanations", [])

                # Big Decision Card
                st.divider()
                c1, c2, c3 = st.columns(3)
                with c1:
                    if final_label == "NORMAL":
                        st.success(f"### Decision: {final_label}")
                    elif final_label == "IN_PROGRESS":
                        st.info(f"### Decision: {final_label}")
                    elif final_label == "RULE_VIOLATION":
                        st.error(f"### Decision: {final_label}")
                    else:
                        st.warning(f"### Decision: {final_label}")

                with c2:
                    st.metric("FSM Verdict", fsm.get("verdict"))
                with c3:
                    st.metric("ML Statistical Flag", "ANOMALOUS" if any(s.get("is_anomaly") for s in ml_scores) else "NORMAL")

                # Explanations
                st.markdown("#### 🗣️ Unified Multi-Sentence Explanations")
                for e in explanations:
                    if final_label == "RULE_VIOLATION":
                        st.error(f"• {e}")
                    elif final_label == "STATISTICAL_ANOMALY":
                        st.warning(f"• {e}")
                    elif final_label == "IN_PROGRESS":
                        st.info(f"• {e}")
                    else:
                        st.success(f"• {e}")

                # ML Evidence Table
                if ml_scores:
                    st.markdown("#### 📈 Statistical Evidence from Evaluated Models")
                    ml_rows = [
                        {
                            "Detector": s.get("detector"),
                            "Raw Score": f"{s.get('raw_score', 0.0):.4f}",
                            "Normalized [0,1]": f"{s.get('norm_score', s.get('normalized_score', 0.0)):.4f}",
                            "Threshold": f"{s.get('threshold', 0.0):.4f}",
                            "Statistically Anomalous": "⚠️ YES" if s.get("is_anomaly") else "✅ NO",
                        }
                        for s in ml_scores
                    ]
                    st.dataframe(pd.DataFrame(ml_rows), width="stretch")

                # Graphviz diagram
                dfa_spec = api.get_workflow_automaton(1, kind="DFA")
                if dfa_spec and "dot" in dfa_spec:
                    st.markdown("#### 🗺️ Traversal Graph")
                    state_path = fsm.get("state_path", [])
                    fail_st = fsm.get("fail_state") if fsm.get("verdict") == "INVALID" else None
                    render_automaton(
                        dot_text=dfa_spec["dot"],
                        visited_states=state_path,
                        failing_state=fail_st,
                        failing_event=fsm.get("fail_event"),
                        fail_from_state=fail_st,
                    )

            except ApiClientError as err:
                st.error(f"Analysis failed: {err}")


# =========================================================================
# TAB 2: BATCH DATASET SPLIT ANALYSIS & DRILL-DOWN
# =========================================================================
with tab_batch:
    st.markdown("### Batch Split Analysis & Detailed Drill-Down")
    st.write(
        "Executes end-to-end hybrid detection across all cases in a selected dataset split, "
        "persisting decisions to the relational database and generating downloadable reports."
    )

    cur_ds_id = st.session_state.get("current_dataset_id")
    if not cur_ds_id:
        st.info("Select or generate a dataset in the sidebar first.")
    else:
        with st.form("batch_detect_form"):
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                batch_split = st.selectbox("Dataset Split:", ["test", "val", "train"])
            with col_b2:
                batch_policy = st.selectbox("ML Consensus:", ["any", "majority", "unanimous"])

            submit_batch = st.form_submit_button("🚀 Run Batch Hybrid Detection", type="primary", width="stretch")
            if submit_batch:
                with st.spinner("Processing batch through DFA validator and active ML models..."):
                    try:
                        b_res = api.detect_batch(
                            dataset_id=cur_ds_id,
                            split=batch_split,
                            ml_policy=batch_policy,
                        )
                        st.success(f"Batch completed! Processed {b_res.get('n_cases')} cases.")
                    except ApiClientError as err:
                        st.error(f"Batch run failed: {err}")

        st.divider()

        # Decision Results Table & Filters
        st.markdown("#### 📋 Stored Hybrid Decisions")
        filter_label = st.selectbox(
            "Filter Decisions by Final Label:",
            ["All", "NORMAL", "RULE_VIOLATION", "STATISTICAL_ANOMALY", "IN_PROGRESS"],
        )

        try:
            results_data = api.list_detect_results(
                dataset_id=cur_ds_id,
                final_label=filter_label if filter_label != "All" else None,
                page_size=50,
            )
            items = results_data.get("items", [])
            st.caption(f"Total matching cases: {results_data.get('pagination', {}).get('total_items', len(items))}")

            if items:
                df_results = pd.DataFrame(items)
                st.dataframe(df_results, width="stretch")

                # Drill-Down
                st.markdown("#### 🔬 Case Drill-Down Inspector")
                selected_case_pk = st.selectbox(
                    "Choose Case PK to inspect in detail:",
                    options=[item["case_pk"] for item in items],
                    format_func=lambda pk: next((f"PK #{pk} | Case: {it.get('case_id')} | Final Label: {it.get('final_label')}" for it in items if it["case_pk"] == pk), str(pk)),
                )

                if selected_case_pk:
                    detail = api.get_detect_result(selected_case_pk)
                    st.caption(f"Case ID: `{detail.get('case_id')}` | Ground Truth Injected: `{detail.get('ground_truth_label')}`")

                    col_d1, col_d2 = st.columns(2)
                    with col_d1:
                        st.info(f"**Final Verdict:** `{detail.get('final_label')}`")
                        st.write(f"**FSM Verdict:** `{detail.get('fsm', {}).get('verdict')}`")
                        st.markdown("**Explanations:**")
                        for ex in detail.get("explanations", []):
                            if isinstance(ex, dict):
                                src_tag = ex.get("source", "diag").upper()
                                st.write(f"• **[{src_tag}]** {ex.get('text', '')}")
                            else:
                                st.write(f"• {ex}")

                    with col_d2:
                        st.markdown("**ML Model Scores:**")
                        case_ml = detail.get("ml", []) or detail.get("ml_scores", [])
                        if not case_ml:
                            st.caption("No statistical ML detector flagged this case.")
                        for s in case_ml:
                            norm_val = s.get('norm_score', s.get('normalized_score', 0.0)) or 0.0
                            raw_val = s.get('raw_score', 0.0) or 0.0
                            flag_tag = "⚠️ Flagged" if s.get('is_anomaly') else "✅ Normal"
                            st.write(
                                f"• **{s.get('detector')}**: Raw={raw_val:.4f}, Norm={norm_val:.3f} ({flag_tag})"
                            )

                st.divider()

                # Report Download buttons per Doc 09 §5
                st.markdown("#### 💾 Download Benchmark Reports")
                col_dl1, col_dl2 = st.columns(2)
                with col_dl1:
                    json_data = api.download_report_data(dataset_id=cur_ds_id, format="json")
                    st.download_button(
                        label="📥 Download Complete Report (JSON)",
                        data=json_data,
                        file_name=f"ps9_report_dataset_{cur_ds_id}.json",
                        mime="application/json",
                        width="stretch",
                    )
                with col_dl2:
                    csv_data = api.download_report_data(dataset_id=cur_ds_id, format="csv")
                    st.download_button(
                        label="📥 Download Summary Report (CSV)",
                        data=csv_data,
                        file_name=f"ps9_report_dataset_{cur_ds_id}.csv",
                        mime="text/csv",
                        width="stretch",
                    )

            else:
                st.info("No hybrid decisions stored yet. Run batch detection using the form above.")

        except ApiClientError as err:
            st.error(f"Could not load results: {err}")

render_provenance_footer(st.session_state.get("current_dataset_info"))
