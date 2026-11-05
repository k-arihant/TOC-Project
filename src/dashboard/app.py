"""PS9 Streamlit Dashboard Main Shell & Home Page.

Pure API client adhering strictly to Doc 09 and Doc 10.
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

import streamlit as st

from src.dashboard.api_client import ApiClient
from src.dashboard.components.provenance import render_provenance_footer

st.set_page_config(
    page_title="TOC Workflow Anomaly Detection",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize API Client in Session State
if "api_client" not in st.session_state:
    st.session_state.api_client = ApiClient()

api: ApiClient = st.session_state.api_client

# ----------------- Sidebar Status & Dataset Context -----------------
with st.sidebar:
    st.title("⚙️ PS9 Platform")
    st.caption("5th Sem Theory of Computation (TOC)")

    # 1. Live Health Check
    health = api.get_health()
    if health.get("status") == "ok":
        st.success(f"🟢 **API Online** (v{health.get('version', '1.0')})")
        if health.get("db_connected"):
            st.caption("💾 Database: Connected")
        else:
            st.caption("⚠️ Database: Disconnected")
    elif health.get("status") == "degraded":
        st.warning("🟡 **API Degraded** (DB unreachable)")
    else:
        st.error(f"🔴 **API Disconnected**\nTarget: `{api.base_url}`")
        st.caption("Ensure `uvicorn src.api.main:app` is running on port 8000.")

    st.divider()

    # 2. Global Dataset Context Selector
    st.subheader("📁 Active Dataset Context")
    try:
        datasets = api.list_datasets()
        if datasets:
            ds_options = {f"#{d['dataset_id']}: {d['name']} ({d['source_kind']})": d["dataset_id"] for d in datasets}
            default_idx = 0
            # If session state already has a selected dataset, preserve index
            cur_id = st.session_state.get("current_dataset_id")
            if cur_id and cur_id in ds_options.values():
                default_idx = list(ds_options.values()).index(cur_id)

            selected_label = st.selectbox(
                "Select active dataset:",
                options=list(ds_options.keys()),
                index=default_idx,
            )
            st.session_state.current_dataset_id = ds_options[selected_label]
            st.session_state.current_dataset_info = next(
                d for d in datasets if d["dataset_id"] == st.session_state.current_dataset_id
            )
        else:
            st.info("No datasets generated yet. Use the **Workflow Data & ML** page to generate or upload one.")
            st.session_state.current_dataset_id = None
            st.session_state.current_dataset_info = None
    except Exception as exc:
        st.caption(f"Could not load datasets: {exc}")
        st.session_state.current_dataset_id = None
        st.session_state.current_dataset_info = None

    st.divider()
    st.caption("Solo Developer Engineering Model")
    st.caption("Repository: `TOC-Project-Git`")


# ----------------- Main Home Page Presentation -----------------

st.title("🛡️ Anomaly Detection in Process Workflows")
st.subheader("Formal Automata & Machine Learning Hybrid System")

st.markdown(
    """
    Welcome to the interactive demonstration interface for **TOC Problem Statement 9 (PS9)**.
    This platform rigorously unites **Formal Language Theory (Automata)** with **Unsupervised & Sequential Machine Learning**
    to deliver transparent, explainable anomaly detection for mission-critical enterprise workflows.
    """
)

# High-level architecture metrics cards
col_a, col_b, col_c, col_d = st.columns(4)
with col_a:
    try:
        workflows = api.get_workflows()
        st.metric("Workflows Registered", len(workflows))
    except Exception:
        st.metric("Workflows", "0")

with col_b:
    try:
        datasets_list = api.list_datasets()
        st.metric("Stored Datasets", len(datasets_list))
    except Exception:
        st.metric("Datasets", "0")

with col_c:
    try:
        models = api.list_models()
        st.metric("Calibrated ML Models", len(models))
    except Exception:
        st.metric("Models", "0")

with col_d:
    try:
        evals = api.list_evaluation_runs()
        st.metric("Benchmark Runs", len(evals))
    except Exception:
        st.metric("Evaluations", "0")

st.divider()

# Core Concept & Duality Section
col_left, col_right = st.columns(2)

with col_left:
    st.markdown("### 🏛️ The Formal Layer (TOC Domain)")
    st.info(
        """
        - **Model:** Complete Deterministic Finite Automaton (DFA) with 13 states + explicit trap state ($S_{\\text{dead}}$).
        - **Capability:** Guarantees **100% precision & recall on structural syntax violations** in $O(n)$ linear time.
        - **Language:** Regular language $L(\\text{DFA})$ over 11 business lifecycle alphabet events.
        - **Formal Contributions:**
          - Thompson NFA with $\\varepsilon$-transitions for payment retry loops.
          - Subset Construction algorithm producing equivalent power-set DFA.
          - Moore's state minimisation algorithm merging equivalent states.
          - Product automaton language equivalence verification ($L(M_1) \\equiv L(M_2)$).
          - Precise failing edge and state identification.
        """
    )

with col_right:
    st.markdown("### 🤖 The Statistical Layer (ML Domain)")
    st.info(
        """
        - **Model:** Feature Extractor (144 features) + Isolation Forest, 1st-Order Markov Chain, and K-Means Centroid Distance.
        - **Capability:** Detects subtle **statistical drift, unusual latency gaps, and excessive retry patterns** that cannot be expressed in regular grammar.
        - **Zero-Leakage Assurance:** Enforces strict case-level stratified splitting and automated leakage assertions.
        - **Calibration:** Non-parametric empirical CDF thresholding on validation negatives for guaranteed target False Positive Rates (e.g. $\\alpha = 0.05$).
        """
    )

st.markdown("### 🔀 The Deterministic Hybrid Fusion Matrix")
st.markdown(
    """
    Unlike black-box ensembles that produce uninterpretable blended scores, PS9 employs a **deterministic 4-row decision matrix**:
    """
)

st.table(
    [
        {"Formal FSM Verdict": "INVALID", "Statistical ML Score": "Any", "Final Decision": "RULE_VIOLATION", "Primary Explanation Source": "Failing transition, offending state, allowed events"},
        {"Formal FSM Verdict": "VALID_COMPLETE", "Statistical ML Score": "Score > Threshold", "Final Decision": "STATISTICAL_ANOMALY", "Primary Explanation Source": "Top feature deviations (e.g., timing gap, retry burst)"},
        {"Formal FSM Verdict": "VALID_COMPLETE", "Statistical ML Score": "Score ≤ Threshold", "Final Decision": "NORMAL", "Primary Explanation Source": "Full formal conformance and normal timing"},
        {"Formal FSM Verdict": "VALID_PREFIX", "Statistical ML Score": "Any", "Final Decision": "IN_PROGRESS", "Primary Explanation Source": "Trace is valid so far, awaiting terminal accepting state"},
    ]
)

st.divider()

# Navigation guidance
st.markdown("### 🧭 Platform Modules (Sidebar Navigation)")
card1, card2, card3 = st.columns(3)
with card1:
    st.markdown("#### 1. [Automata Explorer](Automata_Explorer)")
    st.write("Inspect base DFA, Thompson NFA, Moore minimisation, and step through traces with live red failing edge highlights.")

with card2:
    st.markdown("#### 2. [Workflow Data & ML](Workflow_Data_and_ML)")
    st.write("Generate reproducible datasets, inspect stratified splits, and train/calibrate statistical anomaly detectors.")

with card3:
    st.markdown("#### 3. [Evaluation & Benchmarks](Evaluation)")
    st.write("Review rigorous multi-seed experimental runs comparing FSM-only vs. ML-only vs. Hybrid across Tables R1–R6.")

card4, card5 = st.columns(2)
with card4:
    st.markdown("#### 4. [Hybrid Detection](Hybrid_Detection)")
    st.write("Test ad-hoc event traces live, run batch predictions over dataset splits, and inspect dual-source explanations.")

with card5:
    st.markdown("#### 5. [Packet Validation](Packet_Validation)")
    st.write("Supplementary experiment: Validate real TCP network flows against strict and tolerant TCP state machines.")

render_provenance_footer(st.session_state.get("current_dataset_info"))
