"""Page 2 — Machine Learning Anomaly Inspector & Multi-Model Comparator.
Input a transaction trace and see how all 4 ML algorithms independently score it,
followed by their ensemble average and hybrid conclusion!
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

st.title("Machine Learning Anomaly Inspector")
st.subheader("Multi-Algorithm Scoring: Isolation Forest, Markov, K-Means & Random Forest")

st.markdown(
    """
    Test any transaction trace across all **4 Machine Learning algorithms simultaneously**.
    Each model evaluates the sequence from a unique perspective (tree partitioning, transition probabilities, 
    clustering distance, and supervised classification) and combines them into an **Ensemble Average**.
    """
)

# Text area for inputs (matches Trace Inspector format)
trace_input = st.text_area(
    "Enter Transaction Trace Activities (one per line, or comma-separated):",
    value="OrderCreated\nPaymentInitiated\nPaymentAuthorized\nOrderPacked\nOrderShipped\nOrderDelivered\nOrderClosed",
    height=160,
    help="Type event steps to run through all 4 ML models.",
)

# Parse activities
import re
raw_lines = trace_input.strip().splitlines()
activities = []
for line in raw_lines:
    if not line.strip():
        continue
    parts = re.split(r"[,;]|\s*->\s*", line.strip())
    for p in parts:
        if p.strip():
            activities.append(p.strip())

col_s1, col_s2 = st.columns([3, 2])
with col_s1:
    ml_delay_days = st.slider(
        "Simulated Carrier Transit & Delivery Dwell Time (Days):",
        min_value=1,
        max_value=90,
        value=7,
        step=1,
        help="Baseline delivery duration is ~7 to 10 days. Values >= 80 days simulate severe real-world logistics delay to test ML dwell time sensitivity.",
    )
with col_s2:
    st.write("")
    st.caption("Simulation Mode:")
    if ml_delay_days >= 75:
        st.warning(f"**Abnormal Dwell Delay ({ml_delay_days}d)**: Extreme dwell time outlier.")
    else:
        st.success(f"**Normal Logistics ({ml_delay_days}d)**: Standard timeline.")

col_btn1, col_btn2 = st.columns([1, 2])
with col_btn1:
    run_btn = st.form_submit_button if False else st.button("Run All 4 ML Models", type="primary", width="stretch")

if run_btn:
    if not activities:
        st.warning("Please provide at least one event.")
    else:
        with st.spinner("Extracting features (144 dimensions) and running ML inference across all 4 detectors..."):
            try:
                # Fetch available models deduplicated by detector (exactly 4 algorithms)
                cur_ds_id = st.session_state.get("current_dataset_id")
                raw_models = api.list_models(dataset_id=cur_ds_id) if cur_ds_id else api.list_models()
                unique_models = {}
                for m in raw_models:
                    unique_models[m["detector"]] = m
                models = list(unique_models.values())
                model_ids = [m["model_run_id"] for m in models]

                # Call detection API
                res = api.detect_analyze(
                    workflow_id=1,
                    case_id="interactive-ml-test",
                    activities=activities,
                    model_run_ids=model_ids,
                    ml_policy="any",
                    delivery_delay_days=float(ml_delay_days),
                )

                ml_scores = res.get("ml", [])

                if not ml_scores:
                    st.warning("No ML scores returned. Ensure models are trained.")
                else:
                    st.divider()
                    st.markdown("### Multi-Model Comparison Table")

                    score_rows = []
                    anomaly_flags = []
                    norm_scores = []

                    model_details = {
                        "isolation_forest": ("Isolation Forest", "Unsupervised tree partitioning of feature space"),
                        "markov": ("1st-Order Markov Chain", "Sequence transition log-likelihood probability"),
                        "kmeans": ("K-Means Distance", "Centroid variance distance from normal clusters"),
                        "random_forest": ("Random Forest", "Supervised classification reference"),
                    }

                    for s in ml_scores:
                        det = s.get("detector", "unknown")
                        title, desc = model_details.get(det, (det.title(), "Statistical detector"))
                        raw_sc = s.get("raw_score", 0.0)
                        norm_sc = s.get("norm_score", 0.0)
                        thr = s.get("threshold", 0.95)
                        is_ano = s.get("is_anomaly", False)

                        anomaly_flags.append(is_ano)
                        norm_scores.append(norm_sc)

                        verdict_badge = "ANOMALY DETECTED" if is_ano else "NORMAL"

                        score_rows.append(
                            {
                                "Model Algorithm": title,
                                "Core Technique": desc,
                                "Raw Score": f"{raw_sc:.4f}",
                                "Normalized Score [0-1]": f"{norm_sc:.4f}",
                                "Decision Threshold": f"{thr:.4f}",
                                "Individual Verdict": verdict_badge,
                            }
                        )

                    st.dataframe(pd.DataFrame(score_rows), width="stretch")

                    # Ensemble Summary Cards
                    st.divider()
                    st.markdown("### Ensemble Aggregation (Core ML Logic)")

                    avg_score = sum(norm_scores) / max(1, len(norm_scores))
                    n_flagged = sum(1 for f in anomaly_flags if f)

                    col_c1, col_c2, col_c3 = st.columns(3)
                    with col_c1:
                        st.metric("Ensemble Average Score", f"{avg_score:.4f}", delta="Normal" if avg_score < 0.90 else "Elevated Risk", delta_color="inverse")
                    with col_c2:
                        st.metric("Voting Consensus", f"{n_flagged} of {len(ml_scores)} Models Flagged", delta=f"{n_flagged} Flags", delta_color="inverse")
                    with col_c3:
                        final_ml_verdict = "STATISTICAL ANOMALY" if (n_flagged >= 2 or avg_score >= 0.90) else "NORMAL PROCESS"
                        st.metric("Aggregated ML Verdict", final_ml_verdict)

                    # Model Insights & Explanations
                    st.markdown("#### Model Interpretability & Evidence")
                    exps = res.get("explanations", [])
                    for exp in exps:
                        st.info(f"• {exp}")

            except ApiClientError as err:
                st.error(f"Inference failed: {err}")

st.divider()

# Reference link to downloadable Kaggle CSVs and PPT benchmarks
with st.expander("Kaggle Dataset Files & Presentation Benchmarks (Click to view paths)"):
    st.markdown(
        """
        - **Kaggle Dataset Directory:** `data/kaggle_ecommerce_workflow_dataset/`
          - `ecommerce_order_events.csv` (3,733 timestamped events)
          - `ecommerce_order_labels.csv` (500 cases with ground-truth labels)
        - **Presentation Benchmarks File:** `docs/MODEL_BENCHMARK_RESULTS_FOR_PPT.md`
        - **CSV Performance Table:** `docs/model_performance_benchmarks.csv`
        """
    )

render_provenance_footer(st.session_state.get("current_dataset_info"))
