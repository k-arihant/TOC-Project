"""Tests for sequence building, stable tie-breaking, and ingestion health checks."""

import pandas as pd

from src.workflow_ml.sequences import build_traces


def test_build_traces_stable_sorting_and_tie_breaking():
    # Input with out-of-order timestamps and equal timestamps
    data = [
        {"case_id": "c1", "activity": "OrderCreated", "timestamp": "2026-01-01T10:00:00Z"},
        {"case_id": "c1", "activity": "PaymentInitiated", "timestamp": "2026-01-01T10:05:00Z"},
        {
            "case_id": "c1",
            "activity": "PaymentAuthorized",
            "timestamp": "2026-01-01T10:05:00Z",
        },  # Equal timestamp!
        {"case_id": "c2", "activity": "OrderCreated", "timestamp": "2026-01-01T09:00:00Z"},
    ]
    df = pd.DataFrame(data)
    traces, report = build_traces(df)

    assert report.n_cases == 2
    assert report.n_events == 4
    assert report.dropped_null_rows == 0

    c1_trace = next(t for t in traces if t.case_id == "c1")
    # Equal timestamp preserves original row order
    assert c1_trace.activities == ["OrderCreated", "PaymentInitiated", "PaymentAuthorized"]


def test_build_traces_drops_null_rows_and_reports():
    data = [
        {"case_id": "c1", "activity": "OrderCreated", "timestamp": "2026-01-01T10:00:00Z"},
        {
            "case_id": None,
            "activity": "PaymentInitiated",
            "timestamp": "2026-01-01T10:05:00Z",
        },  # Null case_id
        {"case_id": "c1", "activity": None, "timestamp": "2026-01-01T10:06:00Z"},  # Null activity
        {"case_id": "c1", "activity": "PaymentAuthorized", "timestamp": None},  # Null timestamp
    ]
    df = pd.DataFrame(data)
    traces, report = build_traces(df)

    assert report.dropped_null_rows == 3
    assert report.n_cases == 1
    assert report.n_events == 1
    assert traces[0].activities == ["OrderCreated"]


def test_build_traces_maps_activities():
    data = [
        {"case_id": "c1", "activity": "OC", "timestamp": "2026-01-01T10:00:00Z"},
        {"case_id": "c1", "activity": "PI", "timestamp": "2026-01-01T10:05:00Z"},
        {"case_id": "c1", "activity": "CustomEvent", "timestamp": "2026-01-01T10:10:00Z"},
    ]
    df = pd.DataFrame(data)
    activity_map = {"OC": "OrderCreated", "PI": "PaymentInitiated"}
    traces, report = build_traces(df, activity_map=activity_map)

    assert traces[0].activities == ["OrderCreated", "PaymentInitiated", "CustomEvent"]
    assert "CustomEvent" in report.unmapped_activities
