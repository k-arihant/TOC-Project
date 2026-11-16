"""Populate the database with a complete synthetic dataset, trained models, and batch hybrid decisions."""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.api.routers.datasets import generate_dataset_endpoint
from src.api.schemas.datasets import GenerateDatasetRequest
from src.api.routers.ml import _create_detector, load_detector_from_model_run
from src.automata.loader import load_workflow
from src.automata.validator import validate_trace
from src.common.types import Event, Trace
from src.db.repositories.dataset_repo import DatasetRepository
from src.db.repositories.hybrid_repo import HybridRepository
from src.db.repositories.model_repo import ModelRepository
from src.db.repositories.workflow_repo import WorkflowRepository
from src.db.session import SessionLocal, create_tables
from src.hybrid.decision import decide


def _build_trace_from_case(case) -> Trace:
    """Build a Trace domain object from a Case ORM model."""
    events = [
        Event(
            case_id=case.case_id,
            activity=e.activity,
            timestamp=e.ts or datetime.now(timezone.utc),
            attributes=e.attributes or {},
        )
        for e in sorted(case.events, key=lambda x: x.seq_index)
    ]
    return Trace(case_id=case.case_id, events=events)


def populate() -> None:
    os.chdir(ROOT_DIR)
    print(f"[Populate] Working directory set to: {os.getcwd()}")
    print("[Populate] Connecting to database...")
    create_tables()
    db = SessionLocal()

    ds_repo = DatasetRepository(db)
    m_repo = ModelRepository(db)
    wf_repo = WorkflowRepository(db)
    h_repo = HybridRepository(db)

    try:
        # Check if workflow exists
        wf = wf_repo.get_by_name_and_version("Online Order & Payment Lifecycle", "1.0.0")
        if not wf:
            from scripts.seed_db import seed_database
            seed_database()
            wf = wf_repo.get_by_name_and_version("Online Order & Payment Lifecycle", "1.0.0")

        wf_id = wf.workflow_id
        dfa = load_workflow("workflows/order_payment/workflow.yaml")

        # 1. Generate primary realistic dataset if no dataset with cases exists
        datasets = ds_repo.list_datasets()
        active_ds = None
        for d in datasets:
            if len(d.cases) > 0:
                active_ds = d
                break

        if not active_ds:
            print("[Populate] Generating synthetic workflow dataset with 500 cases (300 train / 100 val / 100 test)...")
            req = GenerateDatasetRequest(
                workflow_id=wf_id,
                name="Order_Payment_Production_Sim_v1",
                seed=42,
                n_train=300,
                n_val=100,
                n_test=100,
                anomaly_rate=0.15,
            )
            res = generate_dataset_endpoint(req, db)
            active_ds = ds_repo.get_dataset(res.dataset_id)
            print(f"[Populate] Created dataset #{active_ds.dataset_id} with {len(active_ds.cases)} cases.")
        else:
            print(f"[Populate] Found existing populated dataset #{active_ds.dataset_id} with {len(active_ds.cases)} cases.")

        ds_id = active_ds.dataset_id

        # 2. Train and calibrate the 4 models if not already trained
        existing_models = m_repo.list_model_runs(dataset_id=ds_id)
        trained_detectors = {m.detector for m in existing_models}

        train_traces = ds_repo.get_traces_for_dataset(ds_id, split="train")
        val_traces = ds_repo.get_traces_for_dataset(ds_id, split="val")
        test_traces = ds_repo.get_traces_for_dataset(ds_id, split="test")

        detector_configs = [
            ("isolation_forest", {"n_estimators": 100}, 0.05),
            ("markov", {}, 0.05),
            ("kmeans", {"n_clusters": 5}, 0.05),
            ("random_forest", {"n_estimators": 50}, 0.05),
        ]

        for det_name, params, target_fpr in detector_configs:
            if det_name in trained_detectors:
                print(f"[Populate] Detector '{det_name}' already trained. Skipping.")
                continue

            print(f"[Populate] Training and calibrating '{det_name}'...")
            det = _create_detector(det_name, seed=42, params=params)

            if det_name == "random_forest":
                labels = [
                    1 if getattr(c, "label_class", "normal") in ("rule_violation", "statistical_anomaly") else 0
                    for c in active_ds.cases if c.split == "train"
                ]
                det.fit_supervised(train_traces, labels)
            else:
                clean_train = [t for t, c in zip(train_traces, [c for c in active_ds.cases if c.split == "train"]) if c.label_class == "normal"]
                det.fit(clean_train if clean_train else train_traces)

            # Calibrate threshold on validation normal traces
            clean_val = [t for t, c in zip(val_traces, [c for c in active_ds.cases if c.split == "val"]) if c.label_class == "normal"]
            det.calibrate(clean_val if clean_val else val_traces, target_fpr=target_fpr)

            # Save model run
            run_obj = m_repo.create_model_run(
                dataset_id=ds_id,
                detector=det_name,
                params=params,
                seed=42,
                target_fpr=target_fpr,
                threshold=det.threshold,
                artifact=det.to_bytes(),
            )
            print(f"[Populate] Saved model run #{run_obj.model_run_id} ({det_name}) with threshold {det.threshold:.4f}.")

            # Record predictions on test traces
            test_scores = det.score(test_traces)
            for trace, score in zip(test_traces, test_scores):
                case_obj = ds_repo.get_case(ds_id, trace.case_id)
                if case_obj:
                    m_repo.record_prediction(
                        case_pk=case_obj.case_pk,
                        model_run_id=run_obj.model_run_id,
                        score=score,
                    )

        # 3. Pre-compute hybrid batch decisions for test traces
        all_models = m_repo.list_model_runs(dataset_id=ds_id)
        active_detectors = [load_detector_from_model_run(m) for m in all_models]

        test_cases = [c for c in active_ds.cases if c.split == "test"]
        print(f"[Populate] Running hybrid decision fusion over {len(test_cases)} test cases...")

        # Get automaton_id for FSM result recording
        auto = wf_repo.get_automaton_by_kind(wf_id, "DFA")
        automaton_id = auto.automaton_id if auto else 1

        for c in test_cases:
            existing_dec = h_repo.get_decision_by_case(c.case_pk)
            if existing_dec:
                continue

            activities = [e.activity for e in sorted(c.events, key=lambda x: x.seq_index)]
            fsm_res = validate_trace(dfa=dfa, case_id=c.case_id, activities=activities)

            # Record FSM result
            fsm_model = h_repo.record_fsm_result(c.case_pk, automaton_id, fsm_res)

            # Build trace and score with all detectors
            trace = _build_trace_from_case(c)
            pred_ids = []
            scores = []

            # Check for existing predictions first
            existing_preds = m_repo.get_predictions_by_case(c.case_pk)
            existing_pred_map = {p.model_run_id: p for p in existing_preds}

            for model_run, det in zip(all_models, active_detectors):
                try:
                    s_list = det.score([trace])
                    if s_list:
                        scores.append(s_list[0])
                        # Only record prediction if it doesn't already exist
                        if model_run.model_run_id in existing_pred_map:
                            pred_ids.append(existing_pred_map[model_run.model_run_id].prediction_id)
                        else:
                            pred = m_repo.record_prediction(
                                case_pk=c.case_pk,
                                model_run_id=model_run.model_run_id,
                                score=s_list[0],
                            )
                            pred_ids.append(pred.prediction_id)
                except Exception:
                    pass

            hybrid_res = decide(fsm=fsm_res, scores=scores, policy="any")

            h_repo.record_decision(
                case_pk=c.case_pk,
                fsm_result_id=fsm_model.fsm_result_id,
                decision=hybrid_res,
                ml_policy="any",
                prediction_ids=pred_ids,
            )

        db.commit()
        print("[Populate] Database populated successfully with full rich data!")

    except Exception as exc:
        db.rollback()
        print(f"[Populate] Error populating database: {exc}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    populate()
