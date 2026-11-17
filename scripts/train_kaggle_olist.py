"""Pipeline to ingest Kaggle Olist Brazilian E-Commerce dataset, train all 4 ML models,
and evaluate efficiency stats across Formal DFA, Pure ML, and Hybrid Decision Engine.
"""

import datetime
import io
import json
import os
import sys
import urllib.request
from pathlib import Path

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import numpy as np
import pandas as pd

from src.api.routers.evaluation import run_evaluation
from src.api.routers.ml import train_model
from src.api.schemas.evaluation import EvaluationRunRequest
from src.api.schemas.ml import TrainModelRequest
from src.common.types import Event, Trace
from src.db.models import Dataset
from src.db.repositories.dataset_repo import DatasetRepository
from src.db.repositories.evaluation_repo import EvaluationRepository
from src.db.repositories.model_repo import ModelRepository
from src.db.session import SessionLocal


def fetch_or_load_olist_data() -> pd.DataFrame:
    """Download or load cached Olist orders data."""
    cache_path = ROOT_DIR / "data" / "kaggle_olist" / "olist_orders_sample.csv"
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    if cache_path.exists():
        print(f"[1/5] Loading cached Olist data from {cache_path}...")
        return pd.read_csv(cache_path)

    print("[1/5] Downloading real Olist orders from Kaggle/GitHub mirror...")
    url = "https://raw.githubusercontent.com/kumarchitransh07/Data-Lake-for-E-Commerce-Analytics/main/olist_orders_dataset.csv"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        # Read first 4000 rows
        lines = [resp.readline().decode("utf-8") for _ in range(4000)]
    
    df = pd.read_csv(io.StringIO("".join(lines)))
    df.to_csv(cache_path, index=False)
    print(f"      Cached {len(df)} Olist orders to {cache_path}")
    return df


def build_traces_from_olist(df: pd.DataFrame):
    """Transform Olist orders into formal workflow traces with labels."""
    print("[2/5] Transforming Olist orders into process workflow event traces...")

    df["purchase"] = pd.to_datetime(df["order_purchase_timestamp"])
    df["approved"] = pd.to_datetime(df["order_approved_at"])
    df["carrier"] = pd.to_datetime(df["order_delivered_carrier_date"])
    df["delivered"] = pd.to_datetime(df["order_delivered_customer_date"])
    df["estimated"] = pd.to_datetime(df["order_estimated_delivery_date"])
    df["delivery_days"] = (df["delivered"] - df["purchase"]).dt.total_seconds() / 86400.0

    cases = []
    
    # 1. Normal delivered orders (timely, 5-18 days)
    normal_df = df[
        (df["order_status"] == "delivered")
        & df["approved"].notna()
        & df["carrier"].notna()
        & df["delivered"].notna()
        & (df["carrier"] > df["approved"])
        & (df["delivered"] > df["carrier"])
        & (df["delivery_days"] >= 4)
        & (df["delivery_days"] <= 20)
    ].copy()

    # 2. Timing/Dwell Anomalies (valid path, but delivery took 32 to 75 days or extreme carrier delay)
    timing_df = df[
        (df["order_status"] == "delivered")
        & df["approved"].notna()
        & df["carrier"].notna()
        & df["delivered"].notna()
        & (df["carrier"] > df["approved"])
        & (df["delivered"] > df["carrier"])
        & (df["delivery_days"] > 30)
    ].copy()

    # 3. Rule Violations (grammar/state violations: missing approval, cancelled after ship, or inverted)
    # We also synthesize genuine workflow violations from canceled/irregular orders
    violation_df = df[
        df["order_status"].isin(["canceled", "unavailable"])
        | (df["approved"].isna() & df["delivered"].notna())
    ].copy()

    print(f"      Pools found -> Normal: {len(normal_df)}, Severe Timing Delay: {len(timing_df)}, Rule Violations: {len(violation_df)}")

    # Sample balanced set: 700 train (normal), 150 val, 150 test
    n_train_normal = 700
    n_val_normal, n_test_normal = 100, 100
    n_val_timing, n_test_timing = 20, 20
    n_val_rule, n_test_rule = 20, 20

    selected_normal = normal_df.sample(n=min(len(normal_df), n_train_normal + n_val_normal + n_test_normal), random_state=42)
    selected_timing = timing_df.sample(n=min(len(timing_df), n_val_timing + n_test_timing), random_state=42)
    selected_violation = violation_df.sample(n=min(len(violation_df), n_val_rule + n_test_rule), random_state=42)

    # Compile traces
    all_traces = []

    # Helper to construct trace events
    def make_events(cid, t_purch, t_appr, t_carr, t_deliv, is_cancel=False, is_skip_pay=False):
        evs = []
        # Step 1: OrderCreated
        t0 = t_purch
        evs.append(Event(case_id=cid, activity="OrderCreated", timestamp=t0))

        if not is_skip_pay:
            # Step 2: PaymentInitiated
            t1 = t0 + datetime.timedelta(seconds=5)
            evs.append(Event(case_id=cid, activity="PaymentInitiated", timestamp=t1))

            # Step 3: PaymentAuthorized
            t2 = t_appr if pd.notna(t_appr) else t1 + datetime.timedelta(minutes=30)
            if t2 <= t1:
                t2 = t1 + datetime.timedelta(minutes=10)
            evs.append(Event(case_id=cid, activity="PaymentAuthorized", timestamp=t2))
        else:
            t2 = t0

        if is_cancel:
            evs.append(Event(case_id=cid, activity="OrderCancelled", timestamp=t2 + datetime.timedelta(hours=2)))
            return evs

        # Step 4: OrderPacked
        t3 = t_carr - datetime.timedelta(hours=4) if pd.notna(t_carr) else t2 + datetime.timedelta(hours=12)
        if t3 <= t2:
            t3 = t2 + datetime.timedelta(hours=1)
        evs.append(Event(case_id=cid, activity="OrderPacked", timestamp=t3))

        # Step 5: OrderShipped
        t4 = t_carr if pd.notna(t_carr) else t3 + datetime.timedelta(hours=6)
        if t4 <= t3:
            t4 = t3 + datetime.timedelta(hours=2)
        evs.append(Event(case_id=cid, activity="OrderShipped", timestamp=t4))

        # Step 6: OrderDelivered
        t5 = t_deliv if pd.notna(t_deliv) else t4 + datetime.timedelta(days=7)
        if t5 <= t4:
            t5 = t4 + datetime.timedelta(days=1)
        evs.append(Event(case_id=cid, activity="OrderDelivered", timestamp=t5))

        # Step 7: OrderClosed
        t6 = t5 + datetime.timedelta(hours=24)
        evs.append(Event(case_id=cid, activity="OrderClosed", timestamp=t6))
        return evs

    # Add Normal traces
    for idx, row in selected_normal.reset_index().iterrows():
        split = "train" if idx < n_train_normal else ("val" if idx < n_train_normal + n_val_normal else "test")
        cid = f"olist-norm-{row['order_id'][:12]}"
        evs = make_events(cid, row["purchase"], row["approved"], row["carrier"], row["delivered"])
        all_traces.append({
            "case_id": cid,
            "label_class": "normal",
            "anomaly_type": None,
            "split": split,
            "events": evs,
        })

    # Add Timing/Dwell Outliers
    for idx, row in selected_timing.reset_index().iterrows():
        split = "val" if idx < n_val_timing else "test"
        cid = f"olist-delay-{row['order_id'][:12]}"
        evs = make_events(cid, row["purchase"], row["approved"], row["carrier"], row["delivered"])
        all_traces.append({
            "case_id": cid,
            "label_class": "statistical_anomaly",
            "anomaly_type": "dwell_time_anomaly",
            "split": split,
            "events": evs,
        })

    # Add Rule Violations
    for idx, row in selected_violation.reset_index().iterrows():
        split = "val" if idx < n_val_rule else "test"
        is_skip = (idx % 2 == 0)
        cid = f"olist-viol-{row['order_id'][:12]}"
        evs = make_events(
            cid, row["purchase"], row["approved"], row["carrier"], row["delivered"],
            is_cancel=(not is_skip), is_skip_pay=is_skip
        )
        all_traces.append({
            "case_id": cid,
            "label_class": "rule_violation",
            "anomaly_type": "skip_payment" if is_skip else "order_cancelled",
            "split": split,
            "events": evs,
        })

    print(f"      Total generated dataset traces: {len(all_traces)}")
    return all_traces


def ingest_to_database(traces: list) -> int:
    """Store the Olist dataset into SQLite ps9.db."""
    print("[3/5] Ingesting Kaggle Olist dataset into Database (ps9.db)...")
    db = SessionLocal()
    repo = DatasetRepository(db)

    # Check if existing dataset with this name exists, delete if so to re-populate
    existing = db.query(Dataset).filter(Dataset.name == "Kaggle_Olist_Brazilian_ECommerce_v1").first()
    if existing:
        print(f"      Dataset already exists (ID: {existing.dataset_id}). Replacing...")
        from src.db.models import (
            Case,
            EvaluationRunModel,
            EvaluationTypeMetricModel,
            EventLog,
            HybridDecisionModel,
            MlPrediction,
            ModelRun,
        )
        eval_ids = [r.eval_id for r in db.query(EvaluationRunModel).filter(EvaluationRunModel.dataset_id == existing.dataset_id).all()]
        if eval_ids:
            db.query(EvaluationTypeMetricModel).filter(EvaluationTypeMetricModel.eval_id.in_(eval_ids)).delete(synchronize_session=False)
            db.query(EvaluationRunModel).filter(EvaluationRunModel.dataset_id == existing.dataset_id).delete(synchronize_session=False)
        m_ids = [m.model_run_id for m in db.query(ModelRun).filter(ModelRun.dataset_id == existing.dataset_id).all()]
        if m_ids:
            db.query(MlPrediction).filter(MlPrediction.model_run_id.in_(m_ids)).delete(synchronize_session=False)
            db.query(ModelRun).filter(ModelRun.dataset_id == existing.dataset_id).delete(synchronize_session=False)
        case_pks = [c.case_pk for c in existing.cases]
        if case_pks:
            db.query(HybridDecisionModel).filter(HybridDecisionModel.case_pk.in_(case_pks)).delete(synchronize_session=False)
            db.query(EventLog).filter(EventLog.case_pk.in_(case_pks)).delete(synchronize_session=False)
            db.query(Case).filter(Case.dataset_id == existing.dataset_id).delete(synchronize_session=False)
        db.delete(existing)
        db.commit()

    ds = repo.create_dataset(
        workflow_id=1,
        name="Kaggle_Olist_Brazilian_ECommerce_v1",
        source_kind="public_log",
        label_semantics="external",
        seed=42,
        config_hash="olist_brazilian_ecom_2017_2018",
    )

    for item in traces:
        c_obj = repo.add_case(
            dataset_id=ds.dataset_id,
            case_id=item["case_id"],
            label_class=item["label_class"],
            anomaly_type=item["anomaly_type"],
            split=item["split"],
        )
        repo.add_events(c_obj.case_pk, item["events"])

    ds_id = ds.dataset_id
    db.close()
    print(f"      Successfully ingested {len(traces)} cases (Dataset ID: {ds_id})")
    return ds_id


def train_ml_models_on_dataset(dataset_id: int) -> list[int]:
    """Train all 4 ML algorithms on the Kaggle dataset."""
    print("[4/5] Training all 4 Machine Learning models on Kaggle Olist dataset...")
    detectors = [
        ("isolation_forest", 0.05),
        ("markov", 0.05),
        ("kmeans", 0.05),
        ("random_forest", 0.05),
    ]

    model_ids = []
    db = SessionLocal()
    for detector_name, target_fpr in detectors:
        req = TrainModelRequest(
            dataset_id=dataset_id,
            detector=detector_name,
            target_fpr=target_fpr,
            params={},
            seed=42,
        )
        res = train_model(payload=req, db=db)
        model_ids.append(res.model_run_id)
        print(f"      ✔ Trained {detector_name.upper():<18} -> ModelRun ID: {res.model_run_id} (threshold: {res.threshold})")

    db.close()
    return model_ids


def evaluate_and_display_stats(dataset_id: int, model_ids: list[int]):
    """Run full benchmark evaluation and print efficiency stats."""
    print("[5/5] Running Comprehensive Efficiency Benchmark on Test Split...")
    db = SessionLocal()

    eval_req = EvaluationRunRequest(
        dataset_id=dataset_id,
        split="test",
        model_run_ids=model_ids,
        ml_policy="any",
    )
    eval_resp = run_evaluation(payload=eval_req, db=db)

    ev_repo = EvaluationRepository(db)
    runs = ev_repo.list_evaluation_runs(dataset_id=dataset_id)

    # Format into summary table
    print("\n" + "=" * 95)
    print(f"{'DETECTOR / ARCHITECTURE':<24} | {'PRECISION':<10} | {'RECALL':<10} | {'F1-SCORE':<10} | {'FPR':<8} | {'ROC-AUC':<8} | {'LATENCY':<8}")
    print("=" * 95)

    stats_list = []
    for r in runs:
        prec = round(r.tp / max(1, r.tp + r.fp), 4)
        rec = round(r.tp / max(1, r.tp + r.fn), 4)
        f1 = round(2 * prec * rec / max(0.0001, prec + rec), 4)
        fpr = round(r.fp / max(1, r.fp + r.tn), 4)
        auc_str = f"{r.roc_auc:.2f}" if r.roc_auc else "N/A"
        lat_str = f"{r.latency_ms_median:.3f}ms" if r.latency_ms_median else "<1ms"

        det_display = r.detector.replace("_", " ").title()
        if r.detector == "fsm_only":
            det_display = "Gate 1: Pure DFA (TOC)"
        elif r.detector == "hybrid":
            det_display = "Gate 3: Hybrid (TOC+ML)"
        elif r.detector in ("isolation_forest", "markov_chain", "kmeans", "random_forest"):
            det_display = f"Gate 2: {det_display}"

        print(f"{det_display:<24} | {prec * 100:>8.2f}% | {rec * 100:>8.2f}% | {f1 * 100:>8.2f}% | {fpr * 100:>6.2f}% | {auc_str:>8} | {lat_str:>8}")

        stats_list.append({
            "detector": det_display,
            "tp": r.tp,
            "fp": r.fp,
            "tn": r.tn,
            "fn": r.fn,
            "precision": prec,
            "recall": rec,
            "f1": f1,
            "fpr": fpr,
            "roc_auc": r.roc_auc,
            "latency_ms": r.latency_ms_median,
        })

    print("=" * 95)
    db.close()
    return stats_list


def main():
    print("🚀 Starting Kaggle Olist Dataset Ingestion, Model Training & Benchmarking Pipeline\n")
    df = fetch_or_load_olist_data()
    traces = build_traces_from_olist(df)
    ds_id = ingest_to_database(traces)
    mids = train_ml_models_on_dataset(ds_id)
    evaluate_and_display_stats(ds_id, mids)
    print("\n✅ All processes completed successfully! Database ps9.db updated.")


if __name__ == "__main__":
    main()
