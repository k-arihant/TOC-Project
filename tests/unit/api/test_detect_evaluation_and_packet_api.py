"""Unit tests for detect, evaluation, and packet API endpoints."""

from fastapi.testclient import TestClient


def test_detect_analyze_trace(client: TestClient):
    payload = {
        "workflow_id": 1,
        "case_id": "adhoc-detect-1",
        "activities": [
            "OrderCreated",
            "PaymentInitiated",
            "PaymentAuthorized",
            "OrderPacked",
            "OrderShipped",
            "OrderDelivered",
            "OrderClosed",
        ],
        "model_run_ids": [],
        "ml_policy": "any",
    }
    response = client.post("/api/v1/detect/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["final_label"] == "NORMAL"
    assert data["fsm"]["verdict"] == "VALID_COMPLETE"


def test_detect_batch_and_get_results(client: TestClient):
    # Generate dataset
    gen_payload = {
        "workflow_id": 1,
        "name": "Batch Detect DS",
        "seed": 12,
        "n_train": 15,
        "n_val": 5,
        "n_test": 10,
        "anomaly_rate": 0.2,
    }
    gen_resp = client.post("/api/v1/datasets/generate", json=gen_payload)
    ds_id = gen_resp.json()["dataset_id"]

    # Run batch detect
    batch_payload = {
        "dataset_id": ds_id,
        "split": "test",
        "model_run_ids": [],
        "ml_policy": "any",
    }
    batch_resp = client.post("/api/v1/detect/batch", json=batch_payload)
    assert batch_resp.status_code == 200
    n_cases = batch_resp.json()["n_cases"]
    assert n_cases >= 1

    # Query results
    res_resp = client.get(f"/api/v1/detect/results?dataset_id={ds_id}")
    assert res_resp.status_code == 200
    items = res_resp.json()["items"]
    assert len(items) == n_cases

    # Single decision detail
    case_pk = items[0]["case_pk"]
    detail_resp = client.get(f"/api/v1/detect/results/{case_pk}")
    assert detail_resp.status_code == 200
    assert "final_label" in detail_resp.json()


def test_evaluation_run_and_reports(client: TestClient):
    # Generate dataset
    gen_payload = {
        "workflow_id": 1,
        "name": "Eval DS",
        "seed": 77,
        "n_train": 15,
        "n_val": 5,
        "n_test": 10,
        "anomaly_rate": 0.3,
    }
    gen_resp = client.post("/api/v1/datasets/generate", json=gen_payload)
    ds_id = gen_resp.json()["dataset_id"]

    # Run evaluation
    eval_payload = {
        "dataset_id": ds_id,
        "split": "test",
        "model_run_ids": [],
        "ml_policy": "any",
    }
    eval_resp = client.post("/api/v1/evaluation/run", json=eval_payload)
    assert eval_resp.status_code == 201
    eval_ids = eval_resp.json()["eval_ids"]
    assert len(eval_ids) == 3  # fsm_only, ml_only, hybrid

    # List runs
    runs_resp = client.get(f"/api/v1/evaluation/runs?dataset_id={ds_id}")
    assert runs_resp.status_code == 200
    assert len(runs_resp.json()) == 3

    # Download report JSON
    rep_json = client.get(f"/api/v1/reports/{ds_id}?format=json")
    assert rep_json.status_code == 200
    assert rep_json.json()["dataset_id"] == ds_id

    # Download report CSV
    rep_csv = client.get(f"/api/v1/reports/{ds_id}?format=csv")
    assert rep_csv.status_code == 200
    assert "text/csv" in rep_csv.headers["content-type"]


def test_packet_experiments_api(client: TestClient):
    # List experiments initially
    list_resp = client.get("/api/v1/packet/experiments")
    assert list_resp.status_code == 200
