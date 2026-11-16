"""Page 3 — Evaluation & Benchmarks (Empirical Verification & Testing Domain).

Adheres strictly to Doc 09 §1 & Doc 12.
Pure API client: renders FSM-only vs. ML-only vs. Hybrid comparative evaluation metrics from stored DB runs.
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

            run_btn = st.form_submit_button("🚀 Run Comprehensive Evaluation", type="primary", width="stretch")
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
                        st.success("Evaluation completed successfully!")
                        st.session_state.current_eval_data = res
                        st.rerun()
                    except ApiClientError as err:
                        st.error(f"Evaluation failed: {err}")

with col_right:
    st.markdown("### 📜 Evaluation History")
    eval_runs = []
    try:
        eval_runs = api.list_evaluation_runs()
        if not eval_runs:
            st.info("No prior evaluation runs recorded in database. Run one using the form on the left.")
        else:
            df_runs = pd.DataFrame(eval_runs)
            display_cols = [c for c in ["eval_id", "detector", "split", "tp", "fp", "tn", "fn", "latency_ms_median"] if c in df_runs.columns]
            st.dataframe(df_runs[display_cols], width="stretch")

            run_ids = [r.get("eval_id") for r in eval_runs if r.get("eval_id") is not None]
            if run_ids:
                selected_eid = st.selectbox(
                    "Select Stored Evaluation Run Details:",
                    options=run_ids,
                    format_func=lambda eid: next(
                        (f"Run #{eid} | Model: {r.get('detector')} | Split: {r.get('split')} (TP={r.get('tp')}, FP={r.get('fp')})"
                         for r in eval_runs if r.get("eval_id") == eid),
                        str(eid),
                    ),
                )
                if st.button("📥 Load Single Run Detail", width="stretch"):
                    st.session_state.current_selected_run_id = selected_eid
                    st.rerun()

    except Exception as exc:
        st.caption(f"Could not load evaluation history: {exc}")

st.divider()

# =========================================================================
# EVALUATION RESULTS PRESENTATION
# =========================================================================
if not eval_runs:
    st.info("💡 Run an evaluation or seed the database to populate benchmark tables and charts.")
else:
    st.markdown("### 📊 Benchmark Results (Doc 12 Table R1)")

    # Format Table R1 from all stored runs
    summary_rows = []
    chart_input = []
    confusion_models = []

    for r in eval_runs:
        det = r.get("detector", "unknown")
        tp = r.get("tp", 0)
        fp = r.get("fp", 0)
        tn = r.get("tn", 0)
        fn = r.get("fn", 0)
        total = max(1, tp + fp + tn + fn)

        prec = tp / max(1, tp + fp)
        rec = tp / max(1, tp + fn)
        acc = (tp + tn) / total
        f1 = (2 * prec * rec) / max(1e-6, prec + rec)
        fpr = r.get("fpr_valid_variation") if r.get("fpr_valid_variation") is not None else (fp / max(1, fp + tn))
        med_lat = r.get("latency_ms_median", 0.0) or 0.0
        p95_lat = r.get("latency_ms_p95", 0.0) or 0.0

        model_label = {
            "fsm_only": "Formal FSM Only",
            "ml_only": "Statistical ML Only",
            "hybrid": "Hybrid Fusion (FSM+ML)",
            "isolation_forest": "Isolation Forest",
            "markov": "Markov Sequence Model",
            "kmeans": "K-Means Distance",
            "random_forest": "Random Forest (Supervised)",
        }.get(det, det.replace("_", " ").title())

        summary_rows.append(
            {
                "Run ID": r.get("eval_id"),
                "Detection Model": model_label,
                "Split": r.get("split", "test"),
                "Accuracy": f"{acc:.3f}",
                "Precision": f"{prec:.3f}",
                "Recall": f"{rec:.3f}",
                "F1-Score": f"{f1:.3f}",
                "FPR (Valid Variations)": f"{fpr:.2%}",
                "Median Latency (ms)": f"{med_lat:.3f}",
                "p95 Latency (ms)": f"{p95_lat:.3f}",
            }
        )

        chart_input.append(
            {
                "model": model_label,
                "precision": round(prec, 3),
                "recall": round(rec, 3),
                "f1": round(f1, 3),
                "fpr": round(fpr, 3),
            }
        )

        confusion_models.append(
            {
                "name": model_label,
                "matrix": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
            }
        )

    st.dataframe(pd.DataFrame(summary_rows), width="stretch")

    # Bar chart comparison
    st.markdown("#### 📈 Multi-Model Comparative Performance")
    render_benchmark_comparison_bar(chart_input)

    # Confusion Matrices
    st.markdown("### 🔲 Confusion Matrices")
    mat_cols = st.columns(min(3, max(1, len(confusion_models))))
    for idx, cm in enumerate(confusion_models[:6]):
        with mat_cols[idx % len(mat_cols)]:
            render_confusion_matrix(matrix=cm["matrix"], title=cm["name"])

    # Per-Type Recall Breakdown
    st.markdown("### 🎯 Per-Anomaly-Type Recall Breakdown (Doc 12 Table R2)")
    st.write(
        "Demonstrates which specific mutation classes (e.g., event skipped, illegal sequence, excessive retries, slow timing gaps) "
        "are successfully flagged by each approach."
    )

    # Check for selected run's type metrics
    sel_id = st.session_state.get("current_selected_run_id") or (eval_runs[0].get("eval_id") if eval_runs else None)
    type_metrics_found = []
    if sel_id:
        try:
            detail = api.get_evaluation_run(sel_id)
            raw_tm = detail.get("type_metrics", [])
            for tm in raw_tm:
                n_c = tm.get("n_cases", 0)
                n_d = tm.get("n_detected", 0)
                rec = n_d / max(1, n_c)
                type_metrics_found.append({
                    "anomaly_type": tm.get("anomaly_type", "unknown").replace("_", " ").title(),
                    "recall": rec,
                    "cases": n_c,
                    "detected": n_d,
                })
        except Exception:
            pass

    if type_metrics_found:
        render_recall_by_anomaly_type(type_metrics_found)
    else:
        st.info("Per-type recall breakdown available when detailed anomaly taxonomy metadata is present in the run.")

    st.markdown("### 💡 Formal Analysis & Viva Defense Insights")
    st.info(
        """
        - **Why FSM-Only cannot detect statistical anomalies:** A finite automaton decides membership in $L(G)$. If a trace undergoes 8 payment retries but every transition is syntactically valid, $\\delta^*(S_0, w) \\in F$, so the FSM verdict is strictly `VALID`. It lacks a clock and memory to count unbounded retries or measure timing.
        - **Why ML-Only flags valid variations:** Machine learning models trained on typical flows assign high anomaly scores to rare, legitimate business variations (such as returns/refunds), causing unwanted false positives ($FPR > 0$).
        - **The Hybrid Advantage:** The hybrid matrix keeps formal grammar violations and statistical anomalies separate. It attains **zero false positives on valid variations** while catching timing anomalies that bypass the automaton!
        """
    )

render_provenance_footer(st.session_state.get("current_dataset_info"))
