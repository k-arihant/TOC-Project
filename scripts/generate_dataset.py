"""Dataset generation script producing events.csv, labels.csv, and meta.json."""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to sys.path so script can be run directly
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd

from src.workflow_ml.ingest import traces_to_dataframe
from src.workflow_ml.injector import AnomalyInjector
from src.workflow_ml.simulator import WorkflowSimulator, load_simulator_config
from src.workflow_ml.splits import split_cases


def compute_config_hash(config_path: Path) -> str:
    """Compute SHA256 hash of configuration file for provenance."""
    if not config_path.exists():
        return "default"
    with open(config_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]


def generate(seed: int, config_path: Path, n_cases: int, out_dir: Path) -> None:
    """Generate reproducible event log dataset."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg = load_simulator_config(config_path)

    print(f"Generating synthetic workflow dataset (seed={seed}, n_cases={n_cases})...")
    simulator = WorkflowSimulator(config=cfg, seed=seed)
    raw_cases = simulator.generate_dataset(n_cases=n_cases)

    print("Injecting controlled rule violations and statistical anomalies with DFA verification...")
    injector = AnomalyInjector(config=cfg, seed=seed)
    cases = injector.inject_anomalies(raw_cases)

    print("Performing stratified case-level splitting...")
    split_map = split_cases(cases, config=cfg, seed=seed)

    # 1. Build events DataFrame (NO labels in events.csv!)
    traces = [c.trace for c in cases]
    events_df = traces_to_dataframe(traces)
    events_file = out_dir / "events.csv"
    events_df.to_csv(events_file, index=False)

    # 2. Build labels DataFrame
    labels_records = []
    for c in cases:
        cid = c.trace.case_id
        labels_records.append(
            {
                "case_id": cid,
                "label_class": c.label_class,
                "anomaly_type": c.anomaly_type,
                "split": split_map.get(cid, "train"),
            }
        )
    labels_df = pd.DataFrame(labels_records)
    labels_file = out_dir / "labels.csv"
    labels_df.to_csv(labels_file, index=False)

    # 3. Compute metadata
    class_counts = labels_df["label_class"].value_counts().to_dict()
    split_counts = labels_df["split"].value_counts().to_dict()
    anom_counts = labels_df["anomaly_type"].value_counts().to_dict()

    meta = {
        "dataset_name": out_dir.name,
        "seed": seed,
        "config_hash": compute_config_hash(config_path),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n_cases": len(cases),
        "n_events": len(events_df),
        "class_distribution": class_counts,
        "split_distribution": split_counts,
        "anomaly_type_distribution": anom_counts,
    }
    meta_file = out_dir / "meta.json"
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    print(f"Dataset generated successfully in: {out_dir}")
    print(f"  • Events: {len(events_df)} rows in {events_file.name}")
    print(f"  • Labels: {len(labels_df)} cases in {labels_file.name}")
    print(f"  • Class distribution: {class_counts}")
    print(f"  • Splits: {split_counts}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic process workflow dataset")
    parser.add_argument("--seed", type=int, default=0, help="Random seed for reproducibility")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/simulator.yaml"),
        help="Path to simulator config",
    )
    parser.add_argument(
        "--n-cases", type=int, default=1000, help="Number of process instances to generate"
    )
    parser.add_argument("--out", type=Path, default=Path("data/sample"), help="Output directory")

    args = parser.parse_args()
    generate(seed=args.seed, config_path=args.config, n_cases=args.n_cases, out_dir=args.out)


if __name__ == "__main__":
    main()
