"""Trace assembly and log parsing with stable tie-breaking and diagnostics."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.common.types import Event, Trace


@dataclass
class IngestReport:
    n_cases: int
    n_events: int
    min_length: int
    median_length: float
    max_length: int
    dropped_null_rows: int
    duplicate_rows_count: int
    unmapped_activities: List[str] = field(default_factory=list)


def build_traces(
    df: pd.DataFrame,
    activity_map: Optional[Dict[str, str]] = None,
) -> Tuple[List[Trace], IngestReport]:
    """Transform raw tabular event log into Trace objects with stable ordering.

    Follows Doc 06 §3 specification:
      1. Drops rows with null case_id, activity, or timestamp.
      2. Parses timestamps into timezone-aware UTC.
      3. Performs stable tie-break sort on (case_id, timestamp, row_idx).
      4. Maps activity names via activity_map (unmapped retained as-is).
      5. Groups by case_id into Trace dataclasses.
      6. Computes comprehensive data health diagnostics.

    Args:
        df: Input DataFrame containing case_id, activity, timestamp columns.
        activity_map: Optional mapping dictionary from aliases/codes to canonical names.

    Returns:
        Tuple of (list_of_traces, ingest_report)
    """
    initial_rows = len(df)
    work_df = df.copy()

    # Retain original row index for stable tie-breaking
    work_df["__row_idx"] = np.arange(len(work_df))

    # Drop nulls in essential columns
    required_cols = ["case_id", "activity", "timestamp"]
    for col in required_cols:
        if col not in work_df.columns:
            raise ValueError(f"Missing required column in event log: '{col}'")

    valid_mask = (
        work_df["case_id"].notna() & work_df["activity"].notna() & work_df["timestamp"].notna()
    )
    dropped_null_rows = int(initial_rows - valid_mask.sum())
    work_df = work_df[valid_mask].copy()

    # Parse timestamps to UTC
    work_df["timestamp"] = pd.to_datetime(work_df["timestamp"], utc=True)

    # Count exact duplicates (same case_id, activity, timestamp)
    dup_mask = work_df.duplicated(subset=["case_id", "activity", "timestamp"], keep="first")
    duplicate_rows_count = int(dup_mask.sum())

    # Map activity names
    unmapped: set[str] = set()
    if activity_map:
        mapped_activities = []
        for act in work_df["activity"]:
            act_str = str(act)
            if act_str in activity_map:
                mapped_activities.append(activity_map[act_str])
            else:
                mapped_activities.append(act_str)
                unmapped.add(act_str)
        work_df["activity"] = mapped_activities

    # Stable tie-break sort: case_id, timestamp, __row_idx
    work_df.sort_values(by=["case_id", "timestamp", "__row_idx"], inplace=True)

    # Identify attribute columns (any non-standard columns)
    standard_cols = {"case_id", "activity", "timestamp", "__row_idx"}
    attr_cols = [c for c in work_df.columns if c not in standard_cols]

    # Group into Traces
    traces: List[Trace] = []
    case_lengths: List[int] = []

    for case_id, group in work_df.groupby("case_id", sort=False):
        events: List[Event] = []
        for _, row in group.iterrows():
            attrs = {}
            for col in attr_cols:
                val = row[col]
                if pd.notna(val):
                    attrs[col] = val

            events.append(
                Event(
                    case_id=str(case_id),
                    activity=str(row["activity"]),
                    timestamp=row["timestamp"].to_pydatetime(),
                    attributes=attrs,
                )
            )

        traces.append(Trace(case_id=str(case_id), events=events))
        case_lengths.append(len(events))

    n_cases = len(traces)
    n_events = sum(case_lengths)
    min_len = int(np.min(case_lengths)) if case_lengths else 0
    max_len = int(np.max(case_lengths)) if case_lengths else 0
    med_len = float(np.median(case_lengths)) if case_lengths else 0.0

    report = IngestReport(
        n_cases=n_cases,
        n_events=n_events,
        min_length=min_len,
        median_length=med_len,
        max_length=max_len,
        dropped_null_rows=dropped_null_rows,
        duplicate_rows_count=duplicate_rows_count,
        unmapped_activities=sorted(list(unmapped)),
    )

    return traces, report
