"""Academic provenance and dataset attribution footer component."""

from typing import Any, Dict, Optional

import streamlit as st


def render_provenance_footer(
    dataset_info: Optional[Dict[str, Any]] = None,
    model_run_id: Optional[int] = None,
    extra_meta: Optional[Dict[str, Any]] = None,
) -> None:
    """Render a standardized provenance footer adhering to Doc 09 §6 & Honesty Rules."""
    st.divider()

    col1, col2 = st.columns([3, 2])
    with col1:
        st.caption("🔒 **System Provenance & Reproducibility Context:**")
        meta_items = []
        if dataset_info:
            ds_id = dataset_info.get("dataset_id", "N/A")
            name = dataset_info.get("name", "Unknown")
            seed = dataset_info.get("seed", 0)
            chash = dataset_info.get("config_hash", "default")
            meta_items.append(f"**Dataset:** `{name}` (ID: #{ds_id})")
            meta_items.append(f"**Seed:** `{seed}`")
            meta_items.append(f"**Config Hash:** `{chash}`")

        if model_run_id is not None:
            meta_items.append(f"**Model Run ID:** `#{model_run_id}`")

        if extra_meta:
            for k, v in extra_meta.items():
                meta_items.append(f"**{k}:** `{v}`")

        if meta_items:
            st.caption(" • ".join(meta_items))
        else:
            st.caption("No active dataset loaded. Connect or select a dataset from the sidebar.")

    with col2:
        st.caption(
            "⚠️ **Academic Transparency Note (TOC PS9):**\n"
            "Anomalies in this workflow are injected by our controlled simulator to establish formal ground-truth. "
            "Zero metrics are hardcoded; all data is rendered dynamically from the live REST API."
        )
