"""Plotly chart visualisations for the Streamlit dashboard."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


def render_score_histogram(
    normal_scores: List[float],
    anomaly_scores: List[float],
    threshold: Optional[float] = None,
    title: str = "Anomaly Score Distribution by Class",
) -> None:
    """Render dual score histogram with calibrated decision threshold."""
    fig = go.Figure()

    if normal_scores:
        fig.add_trace(
            go.Histogram(
                x=normal_scores,
                name="Normal Traces",
                opacity=0.65,
                marker_color="#2ca02c",
                nbinsx=35,
            )
        )

    if anomaly_scores:
        fig.add_trace(
            go.Histogram(
                x=anomaly_scores,
                name="Anomalous Traces",
                opacity=0.65,
                marker_color="#d62728",
                nbinsx=35,
            )
        )

    if threshold is not None:
        fig.add_vline(
            x=threshold,
            line_width=2.5,
            line_dash="dash",
            line_color="#1f77b4",
            annotation_text=f"Threshold: {threshold:.3f}",
            annotation_position="top left",
        )

    fig.update_layout(
        title=title,
        barmode="overlay",
        xaxis_title="Anomaly Score (Higher = More Anomalous)",
        yaxis_title="Trace Count",
        legend=dict(yanchor="top", y=0.99, xanchor="right", x=0.99),
        template="plotly_white",
        margin=dict(l=40, r=40, t=50, b=40),
        height=380,
    )
    st.plotly_chart(fig, use_container_width=True)


def render_roc_pr_curves(
    roc_points: Optional[List[Dict[str, float]]] = None,
    pr_points: Optional[List[Dict[str, float]]] = None,
    roc_auc: Optional[float] = None,
    pr_auc: Optional[float] = None,
) -> None:
    """Render ROC and Precision-Recall curves side-by-side."""
    col1, col2 = st.columns(2)

    with col1:
        fig_roc = go.Figure()
        if roc_points:
            df_roc = pd.DataFrame(roc_points).sort_values(by="fpr")
            fig_roc.add_trace(
                go.Scatter(
                    x=df_roc["fpr"],
                    y=df_roc["tpr"],
                    mode="lines",
                    name=f"ROC (AUC = {roc_auc:.3f})" if roc_auc else "ROC",
                    line=dict(color="#1f77b4", width=2.5),
                )
            )
        # Baseline diagonal
        fig_roc.add_trace(
            go.Scatter(
                x=[0, 1],
                y=[0, 1],
                mode="lines",
                name="Random Chance",
                line=dict(color="grey", dash="dash"),
            )
        )
        fig_roc.update_layout(
            title=f"ROC Curve {f'(AUC = {roc_auc:.3f})' if roc_auc else ''}",
            xaxis_title="False Positive Rate (FPR)",
            yaxis_title="True Positive Rate (TPR)",
            template="plotly_white",
            height=360,
            margin=dict(l=40, r=40, t=50, b=40),
        )
        st.plotly_chart(fig_roc, use_container_width=True)

    with col2:
        fig_pr = go.Figure()
        if pr_points:
            df_pr = pd.DataFrame(pr_points).sort_values(by="recall")
            fig_pr.add_trace(
                go.Scatter(
                    x=df_pr["recall"],
                    y=df_pr["precision"],
                    mode="lines",
                    name=f"PR (AUC = {pr_auc:.3f})" if pr_auc else "PR Curve",
                    line=dict(color="#ff7f0e", width=2.5),
                )
            )
        fig_pr.update_layout(
            title=f"Precision-Recall Curve {f'(AUC = {pr_auc:.3f})' if pr_auc else ''}",
            xaxis_title="Recall",
            yaxis_title="Precision",
            template="plotly_white",
            height=360,
            margin=dict(l=40, r=40, t=50, b=40),
        )
        st.plotly_chart(fig_pr, use_container_width=True)


def render_confusion_matrix(
    matrix: Dict[str, int],
    title: str = "Confusion Matrix",
) -> None:
    """Render a 2x2 confusion matrix heatmap."""
    tn = matrix.get("tn", 0)
    fp = matrix.get("fp", 0)
    fn = matrix.get("fn", 0)
    tp = matrix.get("tp", 0)

    z = [[tn, fp], [fn, tp]]
    x_labels = ["Predicted Normal", "Predicted Anomaly"]
    y_labels = ["Actual Normal", "Actual Anomaly"]

    annotations = []
    for i, row in enumerate(z):
        for j, val in enumerate(row):
            annotations.append(
                dict(
                    x=x_labels[j],
                    y=y_labels[i],
                    text=f"<b>{val}</b>",
                    showarrow=False,
                    font=dict(color="white" if val > (tp + tn) / 4 else "black", size=16),
                )
            )

    fig = go.Figure(
        data=go.Heatmap(
            z=z,
            x=x_labels,
            y=y_labels,
            colorscale="Blues",
            showscale=False,
        )
    )
    fig.update_layout(
        title=title,
        annotations=annotations,
        template="plotly_white",
        height=320,
        margin=dict(l=40, r=40, t=50, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_benchmark_comparison_bar(
    comparison_data: List[Dict[str, Any]],
    title: str = "Performance Metrics Comparison: FSM vs ML vs Hybrid",
) -> None:
    """Render grouped bar chart comparing Precision, Recall, and F1-Score."""
    if not comparison_data:
        st.info("No comparison metrics available.")
        return

    df = pd.DataFrame(comparison_data)
    # Required columns: model, precision, recall, f1, fpr
    melted = df.melt(
        id_vars=["model"],
        value_vars=["precision", "recall", "f1", "fpr"],
        var_name="Metric",
        value_name="Score",
    )

    metric_names = {
        "precision": "Precision",
        "recall": "Recall",
        "f1": "F1-Score",
        "fpr": "False Positive Rate (FPR)",
    }
    melted["Metric"] = melted["Metric"].map(lambda m: metric_names.get(m, m))

    fig = px.bar(
        melted,
        x="Metric",
        y="Score",
        color="model",
        barmode="group",
        title=title,
        color_discrete_sequence=["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"],
        range_y=[0, 1.05],
    )
    fig.update_layout(
        template="plotly_white",
        yaxis_title="Score (0.0 to 1.0)",
        xaxis_title="",
        legend_title="Detection Approach",
        height=400,
        margin=dict(l=40, r=40, t=50, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_recall_by_anomaly_type(
    type_metrics: List[Dict[str, Any]],
    title: str = "Recall Breakdown Across Specific Anomaly Types",
) -> None:
    """Render horizontal bar chart for recall by anomaly type."""
    if not type_metrics:
        st.info("No per-type recall data available.")
        return

    df = pd.DataFrame(type_metrics)
    # Columns expected: anomaly_type, recall, count
    if "anomaly_type" not in df.columns or "recall" not in df.columns:
        return

    df = df.sort_values(by="recall", ascending=True)

    fig = px.bar(
        df,
        x="recall",
        y="anomaly_type",
        orientation="h",
        title=title,
        range_x=[0, 1.05],
        color="recall",
        color_continuous_scale="Viridis",
        text="recall",
    )
    fig.update_traces(texttemplate="%{text:.1%}", textposition="outside")
    fig.update_layout(
        template="plotly_white",
        xaxis_title="Recall (Sensitivity)",
        yaxis_title="Anomaly Mutation Type",
        height=400,
        margin=dict(l=40, r=40, t=50, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)
