"""Page 2 — Workflow Data & Machine Learning (Data & Sequence Modeling Domain).

Adheres strictly to Doc 09 §1 & Doc 05.
Pure API client: generates datasets, views cases, trains detectors, and displays ROC/PR & histograms.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.dashboard.api_client import ApiClient, ApiClientError
from src.dashboard.components.charts import render_roc_pr_curves, render_score_histogram
from src.dashboard.components.provenance import render_provenance_footer

api: ApiClient = st.session_state.get("api_client", ApiClient())

st.title("📊 Workflow Data & Machine Learning")
st.subheader("Synthetic Generation, Stratified Ingestion & Statistical Anomaly Detectors")

tab_manage, tab_cases, tab_train, tab_models = st.tabs(
    [
        "📥 Dataset Generation & Upload",
        "📂 Case & Trace Explorer",
        "🧠 Train & Calibrate Detectors",
        "📈 Model Metrics & Curves",
    ]
)

# =========================================================================
# TAB 1: DATASET GENERATION & UPLOAD
# =========================================================================
with tab_manage:
    st.markdown("### Dataset Generation & Upload")
    st.write(
        "Generate reproducible synthetic datasets using log-normal transition times and controlled ground-truth anomaly injection, "
        "or upload external event logs in standard CSV format."
    )

    col_gen, col_up = st.columns(2)

    with col_gen:
        st.markdown("#### 🎲 Generate Seeded Synthetic Log")
        with st.form("generate_dataset_form"):
            wf_id = st.number_input("Workflow ID", min_value=1, value=1, step=1)
            ds_name = st.text_input("Dataset Name", value="Order_Payment_Synthetic_v1")
            seed = st.number_input("Random Seed (Reproducibility)", min_value=0, value=0, step=1)
            col_s1, col_s2, col_s3 = st.columns(3)
            with col_s1:
                n_train = st.number_input("Train Cases", min_value=10, value=300, step=50)
            with col_s2:
                n_val = st.number_input("Val Cases", min_value=10, value=100, step=25)
            with col_s3:
                n_test = st.number_input("Test Cases", min_value=10, value=100, step=25)

            anomaly_rate = st.slider("Anomaly Injection Rate", min_value=0.05, max_value=0.30, value=0.10, step=0.01)

            submit_gen = st.form_submit_button("⚡ Generate Dataset", type="primary", use_container_width=True)
            if submit_gen:
                with st.spinner("Simulating traces, injecting anomalies, and writing to database..."):
                    try:
                        res = api.generate_dataset(
                            workflow_id=wf_id,
                            name=ds_name,
                            seed=seed,
                            n_train=n_train,
                            n_val=n_val,
                            n_test=n_test,
                            anomaly_rate=anomaly_rate,
                        )
                        st.success(f"Generated Dataset #{res['dataset_id']}: '{res['name']}' ({res['n_cases']} cases)!")
                        st.session_state.current_dataset_id = res["dataset_id"]
                        st.session_state.current_dataset_info = res
                        st.rerun()
                    except ApiClientError as err:
                        st.error(f"Generation failed: {err}")

    with col_up:
        st.markdown("#### 📤 Upload Custom CSV Log")
        with st.form("upload_dataset_form"):
            up_wf_id = st.number_input("Workflow ID", min_value=1, value=1, step=1, key="up_wf")
            up_name = st.text_input("Dataset Name", value="Uploaded_Log_v1")
            events_file = st.file_uploader("Events CSV (`case_id`, `activity`, `timestamp`)", type=["csv"])
            labels_file = st.file_uploader("Optional Labels CSV (`case_id`, `label_class`, `anomaly_type`)", type=["csv"])

            submit_up = st.form_submit_button("⬆️ Upload & Ingest", use_container_width=True)
            if submit_up:
                if not events_file:
                    st.warning("Please select an events CSV file.")
                else:
                    with st.spinner("Ingesting and validating upload..."):
                        try:
                            res = api.upload_dataset(
                                workflow_id=up_wf_id,
                                name=up_name,
                                events_bytes=events_file.getvalue(),
                                events_filename=events_file.name,
                                labels_bytes=labels_file.getvalue() if labels_file else None,
                                labels_filename=labels_file.name if labels_file else None,
                            )
                            st.success(f"Uploaded Dataset #{res['dataset_id']} successfully!")
                            st.session_state.current_dataset_id = res["dataset_id"]
                            st.session_state.current_dataset_info = res
                            st.rerun()
                        except ApiClientError as err:
                            st.error(f"Upload failed: {err}")

    st.divider()
    st.markdown("#### 📚 Available Datasets in Database")
    try:
        all_ds = api.list_datasets()
        if all_ds:
            df_ds = pd.DataFrame(all_ds)
            st.dataframe(df_ds, use_container_width=True)
        else:
            st.info("No datasets available in database.")
    except Exception as exc:
        st.error(f"Could not load datasets: {exc}")


# =========================================================================
# TAB 2: CASE & TRACE EXPLORER
# =========================================================================
with tab_cases:
    st.markdown("### Case & Trace Explorer")
    cur_ds_id = st.session_state.get("current_dataset_id")

    if not cur_ds_id:
        st.info("Please select or generate a dataset from the **Dataset Generation & Upload** tab.")
    else:
        st.markdown(f"**Viewing Dataset ID #{cur_ds_id}**")
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            split_filter = st.selectbox("Filter by Split:", ["All", "train", "val", "test"])
        with col_f2:
            label_filter = st.selectbox("Filter by Class:", ["All", "normal", "rule_violation", "statistical_anomaly"])
        with col_f3:
            page_num = st.number_input("Page:", min_value=1, value=1, step=1)

        try:
            cases_data = api.get_dataset_cases(
                dataset_id=cur_ds_id,
                split=split_filter if split_filter != "All" else None,
                label_class=label_filter if label_filter != "All" else None,
                page=page_num,
                page_size=20,
            )

            cases_list = cases_data.get("items", [])
            pagination = cases_data.get("pagination", {})

            st.caption(
                f"Showing page {pagination.get('page')} of {pagination.get('total_pages')} "
                f"(Total cases: {pagination.get('total_items')})"
            )

            if cases_list:
                df_cases = pd.DataFrame(cases_list)
                st.dataframe(df_cases, use_container_width=True)

                st.markdown("#### 🔍 Inspect Single Case Events")
                selected_pk = st.selectbox(
                    "Choose Case PK to inspect:",
                    options=[c["case_pk"] for c in cases_list],
                    format_func=lambda pk: next((f"PK #{pk} | Case ID: {c['case_id']} | Label: {c['label_class']}" for c in cases_list if c["case_pk"] == pk), str(pk)),
                )

                if selected_pk:
                    detail = api.get_case_detail(selected_pk)
                    events = detail.get("events", [])
                    st.caption(f"Case `{detail.get('case_id')}` | Injected Anomaly Type: `{detail.get('anomaly_type') or 'None'}`")
                    if events:
                        st.dataframe(pd.DataFrame(events), use_container_width=True)
            else:
                st.info("No cases found matching the selected filters.")

        except ApiClientError as err:
            st.error(f"Error fetching cases: {err}")


# =========================================================================
# TAB 3: TRAIN & CALIBRATE DETECTORS
# =========================================================================
with tab_train:
    st.markdown("### Train & Calibrate Anomaly Detectors")
    st.write(
        "Trains statistical models on training negatives (`train` normal traces) and calibrates an empirical decision "
        "threshold on validation negatives (`val` normal traces) for a guaranteed target False Positive Rate (FPR $\\le \\alpha$)."
    )

    cur_ds_id = st.session_state.get("current_dataset_id")
    if not cur_ds_id:
        st.info("Please select or generate a dataset from the **Dataset Generation & Upload** tab first.")
    else:
        with st.form("train_detector_form"):
            st.markdown(f"**Target Dataset:** #{cur_ds_id}")
            detector_choice = st.selectbox(
                "Select Anomaly Detector:",
                [
                    ("isolation_forest", "Isolation Forest (Unsupervised tree-based partitioning)"),
                    ("markov", "1st-Order Markov Sequence Model (Transition log-likelihood)"),
                    ("kmeans", "K-Means Centroid Distance Score (Cluster variance distance)"),
                    ("random_forest", "Supervised Random Forest (Upper bound reference)"),
                ],
                format_func=lambda x: x[1],
            )[0]

            target_fpr = st.slider(
                "Target False Positive Rate (FPR) for ECDF Threshold Calibration (α):",
                min_value=0.01,
                max_value=0.10,
                value=0.05,
                step=0.01,
            )

            st.caption("Hyperparameters (defaults pre-tuned per Doc 05):")
            col_h1, col_h2 = st.columns(2)
            with col_h1:
                n_est = st.number_input("Estimators / Clusters / States", min_value=1, value=100, step=10)
            with col_h2:
                seed = st.number_input("Model Seed", min_value=0, value=0, step=1)

            submit_train = st.form_submit_button("🚀 Train & Calibrate Model", type="primary", use_container_width=True)
            if submit_train:
                with st.spinner(f"Extracting features, fitting {detector_choice}, and calibrating threshold..."):
                    try:
                        trained = api.train_ml_model(
                            dataset_id=cur_ds_id,
                            detector=detector_choice,
                            target_fpr=target_fpr,
                            hyperparameters={"n_estimators": n_est, "random_state": seed},
                        )
                        st.success(
                            f"Model #{trained['model_run_id']} trained! "
                            f"Calibrated Threshold: `{trained.get('threshold_calibrated', 0.0):.4f}` "
                            f"(Validation FPR: `{trained.get('val_fpr', 0.0):.2%}`)"
                        )
                        st.rerun()
                    except ApiClientError as err:
                        st.error(f"Training failed: {err}")


# =========================================================================
# TAB 4: MODEL METRICS & SCORE HISTOGRAMS
# =========================================================================
with tab_models:
    st.markdown("### Trained Model Evaluation & Distributions")
    cur_ds_id = st.session_state.get("current_dataset_id")

    try:
        models = api.list_models(dataset_id=cur_ds_id)
        if not models:
            st.info("No trained models found for this dataset. Train one in the **Train & Calibrate Detectors** tab.")
        else:
            df_m = pd.DataFrame(models)
            st.dataframe(df_m, use_container_width=True)

            selected_mid = st.selectbox(
                "Choose Model Run to Inspect:",
                options=[m["model_run_id"] for m in models],
                format_func=lambda mid: next(
                    f"Run #{mid} | Detector: {m['detector']} | Calibrated Threshold: {m.get('threshold_calibrated', 0.0):.3f}"
                    for m in models if m["model_run_id"] == mid
                ),
            )

            if selected_mid:
                st.markdown(f"#### Performance Analytics for Model #{selected_mid}")
                m_detail = api.get_model_metrics(selected_mid)

                roc_auc = m_detail.get("roc_auc")
                pr_auc = m_detail.get("pr_auc")
                normal_scores = m_detail.get("normal_scores", [])
                anomaly_scores = m_detail.get("anomaly_scores", [])
                threshold = m_detail.get("threshold_calibrated")

                col_a1, col_a2 = st.columns(2)
                col_a1.metric("ROC AUC", f"{roc_auc:.3f}" if roc_auc else "N/A")
                col_a2.metric("PR AUC", f"{pr_auc:.3f}" if pr_auc else "N/A")

                # Score Histogram
                render_score_histogram(
                    normal_scores=normal_scores,
                    anomaly_scores=anomaly_scores,
                    threshold=threshold,
                    title="Anomaly Score Distribution Across Test Traces",
                )

                # ROC and PR Curves
                render_roc_pr_curves(
                    roc_points=m_detail.get("roc_points"),
                    pr_points=m_detail.get("pr_points"),
                    roc_auc=roc_auc,
                    pr_auc=pr_auc,
                )

    except ApiClientError as err:
        st.error(f"Could not load models: {err}")

render_provenance_footer(st.session_state.get("current_dataset_info"))
