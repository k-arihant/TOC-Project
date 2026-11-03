import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure repository root is on sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.research.kmeans_score import KMeansDetector
from src.research.markov import MarkovDetector
from src.workflow_ml.features import FEATURE_SPEC_VERSION
from src.workflow_ml.ingest import ingest_csv
from src.workflow_ml.isolation_forest import IsolationForestDetector
from src.workflow_ml.random_forest import RandomForestDetector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train and calibrate workflow anomaly detection models."
    )
    parser.add_argument(
        "--dataset", type=str, default="data/sample", help="Path to dataset directory."
    )
    parser.add_argument("--seed", type=int, default=0, help="Random seed for model training.")
    parser.add_argument(
        "--out-dir", type=str, default="artifacts/models", help="Directory to save model artifacts."
    )
    parser.add_argument(
        "--target-fpr", type=float, default=0.05, help="Target FPR for threshold calibration."
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dataset_dir = Path(args.dataset)
    events_path = dataset_dir / "events.csv"
    labels_path = dataset_dir / "labels.csv"

    if not events_path.exists():
        raise FileNotFoundError(f"Missing events file: {events_path}")
    if not labels_path.exists():
        raise FileNotFoundError(f"Missing labels file: {labels_path}")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[Train] Loading traces from {events_path}...")
    traces, _report = ingest_csv(events_path)
    trace_by_case = {t.case_id: t for t in traces}

    print(f"[Train] Loading labels from {labels_path}...")
    with open(labels_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        labels_rows = list(reader)

    # Partition cases
    train_normal_traces = []
    train_all_traces = []
    train_labels = []

    val_normal_traces = []
    val_all_traces = []
    val_labels = []

    test_traces = []

    for row in labels_rows:
        cid = str(row["case_id"])
        split = str(row["split"])
        class_label = str(row.get("label_class") or row.get("class_label"))
        is_ano = int(class_label in ("rule_violation", "statistical_anomaly"))

        trace = trace_by_case.get(cid)
        if trace is None:
            continue

        if split == "train":
            train_all_traces.append(trace)
            train_labels.append(is_ano)
            if class_label in ("normal", "valid_variation"):
                train_normal_traces.append(trace)
        elif split == "val":
            val_all_traces.append(trace)
            val_labels.append(is_ano)
            if class_label in ("normal", "valid_variation"):
                val_normal_traces.append(trace)
        elif split == "test":
            test_traces.append(trace)

    print(
        f"[Train] Split breakdown: Train={len(train_all_traces)} ({len(train_normal_traces)} clean), "
        f"Val={len(val_all_traces)} ({len(val_normal_traces)} clean), Test={len(test_traces)}"
    )

    models_info = {}

    # 1. Isolation Forest
    print("\n--- Training Isolation Forest ---")
    if_detector = IsolationForestDetector(random_state=args.seed)
    if_detector.fit(train_normal_traces)
    if_detector.calibrate(val_normal_traces, target_fpr=args.target_fpr)
    val_scores_if = if_detector.score(val_normal_traces)
    achieved_fpr_if = sum(s.is_anomaly for s in val_scores_if) / max(1, len(val_scores_if))
    print(
        f"Calibrated threshold: {if_detector.threshold:.4f} (Achieved val FPR: {achieved_fpr_if:.2%})"
    )
    with open(out_dir / "isolation_forest.pkl", "wb") as f:
        f.write(if_detector.to_bytes())
    models_info["isolation_forest"] = {
        "threshold": if_detector.threshold,
        "achieved_val_fpr": achieved_fpr_if,
        "file": "isolation_forest.pkl",
    }

    # 2. Markov Chain
    print("\n--- Training Markov Model ---")
    markov_detector = MarkovDetector(alpha=1.0, scoring_mode="mean_nll")
    markov_detector.fit(train_normal_traces)
    markov_detector.calibrate(val_normal_traces, target_fpr=args.target_fpr)
    val_scores_mk = markov_detector.score(val_normal_traces)
    achieved_fpr_mk = sum(s.is_anomaly for s in val_scores_mk) / max(1, len(val_scores_mk))
    print(
        f"Calibrated threshold: {markov_detector.threshold:.4f} (Achieved val FPR: {achieved_fpr_mk:.2%})"
    )
    with open(out_dir / "markov.pkl", "wb") as f:
        f.write(markov_detector.to_bytes())
    models_info["markov"] = {
        "threshold": markov_detector.threshold,
        "achieved_val_fpr": achieved_fpr_mk,
        "file": "markov.pkl",
    }

    # 3. K-Means
    print("\n--- Training K-Means ---")
    kmeans_detector = KMeansDetector(n_clusters=5, random_state=args.seed)
    kmeans_detector.fit(train_normal_traces)
    kmeans_detector.calibrate(val_normal_traces, target_fpr=args.target_fpr)
    val_scores_km = kmeans_detector.score(val_normal_traces)
    achieved_fpr_km = sum(s.is_anomaly for s in val_scores_km) / max(1, len(val_scores_km))
    print(
        f"Calibrated threshold: {kmeans_detector.threshold:.4f} (Achieved val FPR: {achieved_fpr_km:.2%})"
    )
    with open(out_dir / "kmeans.pkl", "wb") as f:
        f.write(kmeans_detector.to_bytes())
    models_info["kmeans"] = {
        "threshold": kmeans_detector.threshold,
        "achieved_val_fpr": achieved_fpr_km,
        "file": "kmeans.pkl",
    }

    # 4. Supervised Random Forest Reference
    print("\n--- Training Random Forest (Supervised Reference under injected labels) ---")
    rf_detector = RandomForestDetector(random_state=args.seed)
    rf_detector.fit_supervised(train_all_traces, train_labels)
    rf_detector.calibrate(val_normal_traces, target_fpr=args.target_fpr)
    val_scores_rf = rf_detector.score(val_normal_traces)
    achieved_fpr_rf = sum(s.is_anomaly for s in val_scores_rf) / max(1, len(val_scores_rf))
    print(
        f"Calibrated threshold: {rf_detector.threshold:.4f} (Achieved val FPR: {achieved_fpr_rf:.2%})"
    )
    with open(out_dir / "random_forest.pkl", "wb") as f:
        f.write(rf_detector.to_bytes())
    models_info["random_forest"] = {
        "threshold": rf_detector.threshold,
        "achieved_val_fpr": achieved_fpr_rf,
        "file": "random_forest.pkl",
        "reference_note": "supervised reference under injected labels",
    }

    manifest = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "seed": args.seed,
        "target_fpr": args.target_fpr,
        "feature_spec_version": FEATURE_SPEC_VERSION,
        "dataset": str(dataset_dir),
        "counts": {
            "train_normal": len(train_normal_traces),
            "train_total": len(train_all_traces),
            "val_normal": len(val_normal_traces),
            "val_total": len(val_all_traces),
            "test_total": len(test_traces),
        },
        "models": models_info,
    }

    manifest_path = out_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"\n[Train] Successfully trained and saved all models to {out_dir}")
    print(f"[Train] Manifest saved to {manifest_path}")


if __name__ == "__main__":
    main()
