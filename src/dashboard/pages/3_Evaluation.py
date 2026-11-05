"""Page 3 — Evaluation & Benchmarks (Empirical Verification & Testing Domain).

Adheres strictly to Doc 09 §1 & Doc 12.
Pure API client: renders FSM-only vs. ML-only vs. Hybrid comparative evaluation metrics from stored DB runs.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.dashboard.api_client import ApiClient, ApiClientError
from src.dashboard.components.charts import (
    render_benchmark_comparison_bar,
    render_confusion_matrix,
    render_recall_by_anomaly_type,
)
from src.dashboard.components.provenance import render_provenance_footer

api: ApiClient = st.session_state.get("api_client", ApiClient())

st.title("🏆 Empirical Evaluation & Benchmarks")
st.subheader("Comparative Study: Formal FSM vs. Statistical ML vs. Hybrid Fusion")

st.markdown(
    """
    Rigorously quantifies the detection capabilities of the formal automata engine against statistical models
    and validates the hypothesis that **hybrid fusion achieves superior F1 without compromising zero FPR on valid variations**.
    """
)

cur_ds_id = st.session_state.get("current_dataset_id")

col_left, col_right = st.columns([1, 2])

with col_left:
    st.markdown("### ⚙️ Run New Benchmark")
    if not cur_ds_id:
        st.warning("Select or generate a dataset in the sidebar first.")
    else:
        with st.form("run_eval_form"):
            st.markdown(f"**Target Dataset:** #{cur_ds_id}")
            split_choice = st.selectbox("Evaluation Split:", ["test", "val", "train"])
            ml_policy = st.selectbox("ML Consensus Policy:", ["any", "majority", "unanimous"])

            # Fetch available models for this dataset
            models = []
            try:
                models = api.list_models(dataset_id=cur_ds_id)
            except Exception:
                pass

            model_ids = [m["model_run_id"] for m in models]
            selected_models = st.multiselect(
                "Include ML Model Runs:",
                options=model_ids,
                default=model_ids[:2] if len(model_ids) >= 2 else model_ids,
                format_func=lambda mid: next((f"#{mid} ({m['detector']})" for m in models if m["model_run_id"] == mid), str(mid)),
            )

            record_in_db = st.checkbox("Record run in Database", value=True)

            run_btn = st.form_submit_button("🚀 Run Comprehensive Evaluation", type="primary", use_container_width=True)
            if run_btn:
                with st.spinner("Computing confusion matrices, per-type metrics, and latency across all test traces..."):
                    try:
                        res = api.run_evaluation(
                            dataset_id=cur_ds_id,
                            split=split_choice,
                            model_run_ids=selected_models,
                            ml_policy=ml_policy,
                            record_in_db=record_in_db,
                        )
                        st.success(f"Evaluation Run #{res.get('eval_run_id', 'new')} completed successfully!")
                        st.session_state.current_eval_data = res
                    except ApiClientError as err:
                        st.error(f"Evaluation failed: {err}")

with col_right:
    st.markdown("### 📜 Evaluation History")
    try:
        eval_runs = api.list_evaluation_runs(dataset_id=cur_ds_id)
        if not eval_runs:
            st.info("No prior evaluation runs recorded in database. Run one using the form on the left.")
        else:
            df_runs = pd.DataFrame(eval_runs)
            st.dataframe(df_runs, use_container_width=True)

            selected_eid = st.selectbox(
                "Load Stored Evaluation Run Details:",
                options=[r["eval_run_id"] for r in eval_runs],
                format_func=lambda eid: next((f"Run #{eid} | Split: {r['split']} | Date: {r['created_at']}" for r in eval_runs if r["eval_run_id"] == eid), str(eid)),
            )
            if st.button("📥 Load Run Metrics", use_container_width=True):
                st.session_state.current_eval_data = api.get_evaluation_run(selected_eid)
                st.rerun()

    except Exception as exc:
        st.caption(f"Could not load evaluation history: {exc}")

st.divider()

# =========================================================================
# EVALUATION RESULTS PRESENTATION
# =========================================================================
eval_data = st.session_state.get("current_eval_data")

if not eval_data:
    st.info("💡 Run an evaluation or select an existing evaluation run to populate the benchmark tables and charts.")
else:
    st.markdown("### 📊 Benchmark Results (Doc 12 Table R1)")
    st.caption(
        f"Evaluation Run #{eval_data.get('eval_run_id')} | Evaluated on Split: `{eval_data.get('split')}` | Total Traces: {eval_data.get('n_cases')}"
    )

    models_data = eval_data.get("models", [])
    if models_data:
        # Table R1
        summary_rows = []
        for m in models_data:
            summary_rows.append(
                {
                    "Detection Model": m.get("model_name"),
                    "Accuracy": f"{m.get('accuracy', 0.0):.3f}",
                    "Precision": f"{m.get('precision', 0.0):.3f}",
                    "Recall": f"{m.get('recall', 0.0):.3f}",
                    "F1-Score": f"{m.get('f1_score', 0.0):.3f}",
                    "FPR (Valid Variations)": f"{m.get('fpr_valid_variation', 0.0):.3%}",
                    "Median Latency (ms)": f"{m.get('latency_median_ms', 0.0):.2f}",
                    "p95 Latency (ms)": f"{m.get('latency_p95_ms', 0.0):.2f}",
                }
            )
        st.dataframe(pd.DataFrame(summary_rows), use_container_width=True)

        # Bar chart comparison
        chart_input = [
            {
                "model": m.get("model_name"),
                "precision": m.get("precision", 0.0),
                "recall": m.get("recall", 0.0),
                "f1": m.get("f1_score", 0.0),
                "fpr": m.get("fpr_valid_variation", 0.0),
            }
            for m in models_data
        ]
        render_benchmark_comparison_bar(chart_input)

    st.markdown("### 🔲 Confusion Matrices")
    mat_cols = st.columns(3)
    for idx, m in enumerate(models_data):
        with mat_cols[idx % 3]:
            matrix = m.get("confusion_matrix", {})
            render_confusion_matrix(matrix=matrix, title=f"{m.get('model_name')}")

    st.markdown("### 🎯 Per-Anomaly-Type Recall Breakdown (Doc 12 Table R2)")
    st.write(
        "Demonstrates which specific mutation classes (e.g., event skipped, illegal sequence, excessive retries, slow timing gaps) "
        "are successfully flagged by each approach."
    )
    type_metrics = eval_data.get("type_metrics", [])
    if type_metrics:
        render_recall_by_anomaly_type(type_metrics)
    else:
        st.caption("Per-type recall breakdown available when dataset includes injected anomaly taxonomy metadata.")

    st.markdown("### 💡 Formal Analysis & Viva Defense Insights")
    st.info(
        """
        - **Why FSM-Only cannot detect statistical anomalies:** A finite automaton decides membership in $L(G)$. If a trace undergoes 8 payment retries but every transition is syntactically valid, $\\delta^*(S_0, w) \\in F$, so the FSM verdict is strictly `VALID`. It lacks a clock and memory to count unbounded retries or measure timing.
        - **Why ML-Only flags valid variations:** Machine learning models trained on typical flows assign high anomaly scores to rare, legitimate business variations (such as returns/refunds), causing unwanted false positives ($FPR > 0$).
        - **The Hybrid Advantage:** The hybrid matrix keeps formal grammar violations and statistical anomalies separate. It attains **zero false positives on valid variations** while catching timing anomalies that bypass the automaton!
        """
    )

render_provenance_footer(st.session_state.get("current_dataset_info"))
