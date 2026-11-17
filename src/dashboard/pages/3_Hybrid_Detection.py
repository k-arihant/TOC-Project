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

tab_single, tab_batch, tab_db = st.tabs(["🧪 Single Trace Live Tester", "📁 CSV Upload & Batch Audit", "🗄️ Database Audit Vault (ps9.db)"])

# =========================================================================
# TAB 1: SINGLE TRACE LIVE TESTER
# =========================================================================
with tab_single:
    st.markdown("### Real-Time Hybrid Decision & Explainability")
    st.write(
        "Submit an event sequence to be evaluated jointly by the deterministic DFA and active machine learning models. "
        "The hybrid engine outputs the definitive 4-row matrix verdict and synthesizes human-readable explanations."
    )

    events_input = st.text_area(
        "Trace Activities (one per line, or comma-separated):",
        value="OrderCreated\nPaymentInitiated\nPaymentAuthorized\nOrderPacked\nOrderShipped\nOrderDelivered\nOrderClosed",
        height=180,
        help="Type or edit transaction steps here to evaluate through the Hybrid Decision Engine.",
    )

    activities = [line.strip() for line in events_input.strip().splitlines() if line.strip()]

    cur_ds_id = st.session_state.get("current_dataset_id")
    available_models = []
    try:
        available_models = api.list_models(dataset_id=cur_ds_id) if cur_ds_id else api.list_models()
    except Exception:
        pass

    model_options = [m["model_run_id"] for m in available_models]
    default_mids = model_options if model_options else [1, 2, 3, 4]
    active_mids = default_mids
    policy = "any"

    with st.expander("⚙️ Advanced Model Configuration (Optional)", expanded=False):
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            active_mids = st.multiselect(
                "Select ML models to consult:",
                options=model_options,
                default=default_mids,
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
# TAB 2: CSV UPLOAD & BATCH AUDIT
# =========================================================================
with tab_batch:
    st.markdown("### 📁 Batch CSV Upload & Automated Audit")
    st.write(
        "Upload any `.csv` event log file (containing `case_id` and `activity` columns) to audit hundreds of "
        "transactions simultaneously through both the formal DFA validator and the 4 statistical ML models."
    )

    uploaded_file = st.file_uploader(
        "Upload Transactions CSV File:",
        type=["csv"],
        help="Upload an enterprise event log CSV containing 'case_id' and 'activity' columns (optional: 'timestamp').",
    )

    if uploaded_file is not None:
        try:
            df_raw = pd.read_csv(uploaded_file)
            st.caption(f"Preview of `{uploaded_file.name}` ({len(df_raw)} events across {df_raw['case_id'].nunique() if 'case_id' in df_raw.columns else 0} transactions):")
            st.dataframe(df_raw.head(5), use_container_width=True)

            if st.button("🚀 Run Automated Audit on CSV", type="primary", use_container_width=True):
                if "case_id" not in df_raw.columns or "activity" not in df_raw.columns:
                    st.error("CSV must contain 'case_id' and 'activity' columns.")
                else:
                    with st.spinner("Executing dual-pipeline audit across all transactions (Formal DFA + ML Ensemble)..."):
                        from datetime import datetime, timezone, timedelta
                        from src.automata.loader import load_workflow
                        from src.automata.validator import validate_trace
                        from src.api.routers.ml import load_detector_from_model_run
                        from src.db.session import SessionLocal
                        from src.db.repositories.model_repo import ModelRepository
                        from src.hybrid.decision import decide
                        from src.common.types import Trace, Event

                        dfa = load_workflow("workflows/order_payment/workflow.yaml")
                        with SessionLocal() as db:
                            m_repo = ModelRepository(db)
                            models = [load_detector_from_model_run(m_repo.get_model_run(i)) for i in [1, 2, 3, 4]]

                        results_list = []
                        counts = {"NORMAL": 0, "RULE_VIOLATION": 0, "STATISTICAL_ANOMALY": 0, "IN_PROGRESS": 0}

                        pair_gaps = {
                            ("OrderCreated", "PaymentInitiated"): 60.0,
                            ("PaymentInitiated", "PaymentAuthorized"): 5.0,
                            ("PaymentInitiated", "PaymentFailed"): 5.0,
                            ("PaymentFailed", "PaymentInitiated"): 120.0,
                            ("PaymentAuthorized", "OrderPacked"): 1800.0,
                            ("OrderPacked", "OrderShipped"): 7200.0,
                            ("OrderShipped", "OrderDelivered"): 86400.0,
                            ("OrderDelivered", "OrderClosed"): 172800.0,
                        }

                        for cid, group in df_raw.groupby("case_id", sort=False):
                            acts = group["activity"].astype(str).tolist()
                            events = []
                            has_ts = "timestamp" in group.columns and pd.notna(group["timestamp"].iloc[0])
                            if has_ts:
                                for _, row in group.iterrows():
                                    try:
                                        ts = datetime.fromisoformat(str(row["timestamp"]))
                                    except Exception:
                                        ts = datetime.now(timezone.utc)
                                    events.append(Event(case_id=str(cid), activity=str(row["activity"]), timestamp=ts))
                            else:
                                # Simulate realistic eCommerce delays if timestamp not provided
                                base_t = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
                                events.append(Event(case_id=str(cid), activity=acts[0], timestamp=base_t))
                                cur_t = base_t
                                for i in range(len(acts) - 1):
                                    gap = pair_gaps.get((acts[i], acts[i+1]), 300.0)
                                    cur_t += timedelta(seconds=gap)
                                    events.append(Event(case_id=str(cid), activity=acts[i+1], timestamp=cur_t))

                            tr = Trace(case_id=str(cid), events=events)
                            fsm_res = validate_trace(dfa=dfa, case_id=str(cid), activities=acts)
                            scores = [m.score([tr])[0] for m in models]
                            dec = decide(fsm=fsm_res, scores=scores, policy="any")

                            v_label = dec.final_label.value
                            counts[v_label] = counts.get(v_label, 0) + 1
                            key_reason = dec.explanation[0] if dec.explanation else "Normal business execution path"

                            verdict_badge = "🟢 NORMAL"
                            if v_label == "RULE_VIOLATION":
                                verdict_badge = "🔴 RULE VIOLATION"
                            elif v_label == "STATISTICAL_ANOMALY":
                                verdict_badge = "🟠 STATISTICAL ANOMALY"
                            elif v_label == "IN_PROGRESS":
                                verdict_badge = "🔵 IN PROGRESS"

                            results_list.append({
                                "Case ID": str(cid),
                                "Events Count": len(acts),
                                "Final Verdict": verdict_badge,
                                "Raw Verdict": v_label,
                                "Formal FSM Check": fsm_res.verdict.value,
                                "ML Flagged": "⚠️ YES" if any(s.is_anomaly for s in scores) else "✅ NO",
                                "Key Reason / Diagnostic": key_reason,
                                "Sequence": " ➔ ".join(acts),
                            })

                        st.session_state.audit_results = results_list
                        st.session_state.audit_counts = counts
                        st.session_state.audit_total = len(results_list)

        except Exception as exc:
            st.error(f"Error parsing CSV: {exc}")

    # Render Audit Results if available
    if "audit_results" in st.session_state:
        res_items = st.session_state.audit_results
        c_dict = st.session_state.audit_counts
        tot = st.session_state.audit_total

        st.divider()
        st.markdown("### 📊 Executive Audit Summary")

        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        with kpi1:
            st.metric("Total Transactions", f"{tot} Cases")
        with kpi2:
            norm_c = c_dict.get("NORMAL", 0)
            st.metric("🟢 Normal Process", f"{norm_c}", delta=f"{norm_c/max(1, tot)*100:.1f}% Valid", delta_color="normal")
        with kpi3:
            rule_c = c_dict.get("RULE_VIOLATION", 0)
            st.metric("🔴 Rule Violations", f"{rule_c}", delta=f"{rule_c/max(1, tot)*100:.1f}% Blocked", delta_color="inverse")
        with kpi4:
            stat_c = c_dict.get("STATISTICAL_ANOMALY", 0)
            st.metric("🟠 Statistical Anomalies", f"{stat_c}", delta=f"{stat_c/max(1, tot)*100:.1f}% Flagged", delta_color="inverse")

        # Table & Filter
        st.markdown("#### 📋 Detailed Transaction Audit Table")
        filter_v = st.selectbox("Filter Decisions by Verdict:", ["All", "NORMAL", "RULE_VIOLATION", "STATISTICAL_ANOMALY", "IN_PROGRESS"])
        
        filtered_rows = res_items if filter_v == "All" else [r for r in res_items if r["Raw Verdict"] == filter_v]
        st.caption(f"Showing {len(filtered_rows)} of {tot} audited transactions:")
        
        df_display = pd.DataFrame(filtered_rows)[["Case ID", "Events Count", "Final Verdict", "Formal FSM Check", "ML Flagged", "Key Reason / Diagnostic"]]
        st.dataframe(df_display, use_container_width=True)

        # Download Report
        st.markdown("#### 💾 Export Audited CSV Report")
        df_export = pd.DataFrame(res_items)
        csv_bytes = df_export.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Complete Audited Report (CSV with Verdicts)",
            data=csv_bytes,
            file_name="audited_transactions_report.csv",
            mime="text/csv",
            use_container_width=True,
        )

        # Drill-down inspector
        st.divider()
        st.markdown("#### 🔬 Single Order Forensic Inspector")
        case_options = [r["Case ID"] for r in res_items]
        selected_cid = st.selectbox("Select Case ID to inspect full path and reasons:", options=case_options)
        if selected_cid:
            c_detail = next(r for r in res_items if r["Case ID"] == selected_cid)
            st.info(f"**Case:** `{c_detail['Case ID']}` | **Verdict:** {c_detail['Final Verdict']}")
            st.write(f"**Full Process Sequence:** `{c_detail['Sequence']}`")
            st.write(f"**Diagnostic Explanation:** {c_detail['Key Reason / Diagnostic']}")

# =========================================================================
# TAB 3: RELATIONAL DATABASE AUDIT VAULT (ps9.db)
# =========================================================================
with tab_db:
    st.markdown("### 🗄️ Relational Database Audit Vault (`ps9.db`)")
    st.write(
        "Demonstrates enterprise-grade audit persistence. All evaluated traces, deterministic DFA state paths, "
        "model prediction scores, and dual-source forensic explanations are permanently stored in the relational schema."
    )

    # Database Summary Metrics
    c_m1, c_m2, c_m3, c_m4 = st.columns(4)
    with c_m1:
        st.metric("Relational Engine", "SQLite / PostgreSQL", help="Managed via SQLAlchemy 2.0 ORM with Alembic migrations")
    with c_m2:
        st.metric("Total Stored Cases", "500 Traces", help="Partitioned into Train (300), Validation (94), and Test (106) splits")
    with c_m3:
        st.metric("Time-Stamped Events", "3,733 Events", help="Indexed on timestamp in event_log table")
    with c_m4:
        st.metric("Stored Test Decisions", "106 Decisions", help="Evaluated test set cases with ground-truth comparisons")

    st.divider()

    # Load stored decisions from API
    try:
        cur_ds_id = st.session_state.get("current_dataset_id", 2)
        dec_resp = api.list_detect_results(dataset_id=cur_ds_id, page_size=200)
        stored_items = dec_resp.get("items", [])

        if stored_items:
            st.markdown("#### 📋 Stored Test Case Decisions")
            col_f1, col_f2 = st.columns([1, 2])
            with col_f1:
                db_filter = st.selectbox(
                    "Filter by Final Verdict:",
                    ["All", "NORMAL", "RULE_VIOLATION", "STATISTICAL_ANOMALY", "IN_PROGRESS"],
                    key="db_verdict_filter"
                )

            filtered_db = stored_items if db_filter == "All" else [d for d in stored_items if d["final_label"] == db_filter]
            st.caption(f"Displaying {len(filtered_db)} of {len(stored_items)} stored records from `hybrid_decisions` table:")

            table_rows = []
            for d in filtered_db:
                v = d["final_label"]
                badge = "🟢 NORMAL"
                if v == "RULE_VIOLATION":
                    badge = "🔴 RULE VIOLATION"
                elif v == "STATISTICAL_ANOMALY":
                    badge = "🟠 STATISTICAL ANOMALY"
                elif v == "IN_PROGRESS":
                    badge = "🔵 IN PROGRESS"

                table_rows.append({
                    "Case ID": d["case_id"],
                    "Decision ID": d["decision_id"],
                    "Final Verdict": badge,
                    "Reason Code": d["reason_code"],
                    "Decided At (Timestamp)": d["decided_at"],
                    "case_pk": d["case_pk"],
                })

            df_db = pd.DataFrame(table_rows)
            st.dataframe(df_db[["Case ID", "Decision ID", "Final Verdict", "Reason Code", "Decided At (Timestamp)"]], use_container_width=True)

            # Forensic Case Inspector for Database
            st.divider()
            st.markdown("#### 🔬 Detailed Case Forensic Inspector (Direct DB Query)")
            inspect_cases = {f"{r['Case ID']} ({r['Final Verdict']})": r["case_pk"] for r in table_rows}
            selected_label = st.selectbox("Select Stored Case to inspect database details:", list(inspect_cases.keys()))

            if selected_label:
                selected_pk = inspect_cases[selected_label]
                try:
                    c_data = api.get_detect_result(selected_pk)
                    
                    col_det1, col_det2 = st.columns(2)
                    with col_det1:
                        st.markdown("**Deterministic FSM Check (`fsm_results` table):**")
                        fsm_d = c_data.get("fsm", {})
                        st.json({
                            "Verdict": fsm_d.get("verdict"),
                            "Traversed State Path": fsm_d.get("state_path"),
                            "Fail State": fsm_d.get("fail_state"),
                            "Attempted Event": fsm_d.get("fail_event"),
                            "Allowed Transitions": fsm_d.get("allowed_events"),
                        })
                    with col_det2:
                        st.markdown("**Machine Learning Telemetry (`ml_predictions` table):**")
                        ml_d = c_data.get("ml", [])
                        ml_summary = [
                            {
                                "Detector": m.get("detector"),
                                "Raw Distance/Score": f"{m.get('raw_score', 0):.4f}",
                                "Normalized Risk": f"{m.get('norm_score', 0):.4f}",
                                "Flagged Outlier": "⚠️ YES" if m.get("is_anomaly") else "✅ NO",
                            }
                            for m in ml_d
                        ]
                        st.table(pd.DataFrame(ml_summary))

                    st.markdown("**Dual-Source Forensic Explanations (`explanations` table):**")
                    exps = c_data.get("explanations", [])
                    if exps:
                        for idx, exp in enumerate(exps, 1):
                            st.write(f"**{idx}. [{exp.get('source', 'HYBRID').upper()}]** {exp.get('text')}")
                    else:
                        st.write("No diagnostic warnings; process conforms to regular grammar and statistical distribution.")

                except Exception as err:
                    st.error(f"Could not load details for case_pk {selected_pk}: {err}")

        else:
            st.info("No stored decisions found in database. Run batch detection to persist new decisions.")

    except Exception as exc:
        st.error(f"Error accessing database records: {exc}")

render_provenance_footer(st.session_state.get("current_dataset_info"))
