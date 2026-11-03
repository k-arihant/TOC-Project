"""CSV and tabular event log ingestion functions."""

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import yaml

from src.common.types import Trace
from src.workflow_ml.sequences import IngestReport, build_traces

DEFAULT_MAP_PATH = Path("workflows/order_payment/activity_map.yaml")


def load_activity_map(path: Optional[str | Path] = None) -> Dict[str, str]:
    """Load activity alias mappings from YAML."""
    map_path = Path(path) if path else DEFAULT_MAP_PATH
    if not map_path.exists():
        return {}
    with open(map_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("mappings", {}) if isinstance(data, dict) else {}


def ingest_csv(
    file_path: str | Path,
    activity_map: Optional[Dict[str, str]] = None,
) -> Tuple[List[Trace], IngestReport]:
    """Ingest a CSV event log file into Trace objects."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Event log file not found: {path}")

    df = pd.read_csv(path)
    if activity_map is None:
        activity_map = load_activity_map()

    return build_traces(df, activity_map)


def traces_to_dataframe(traces: List[Trace]) -> pd.DataFrame:
    """Convert a list of Trace objects back into a standard tabular event log DataFrame."""
    rows = []
    for trace in traces:
        for event in trace.events:
            row = {
                "case_id": event.case_id,
                "activity": event.activity,
                "timestamp": event.timestamp.isoformat(),
            }
            if event.attributes:
                for k, v in event.attributes.items():
                    row[k] = v
            rows.append(row)
    return pd.DataFrame(rows)
