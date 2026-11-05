"""Unit tests for datasets and ML training & scoring API endpoints."""

import io

from fastapi.testclient import TestClient


def test_generate_and_list_datasets(client: TestClient):
    payload = {
        "workflow_id": 1,
        "name": "API Test Dataset",
        "seed": 42,
        "n_train": 20,
        "n_val": 10,
        "n_test": 10,
        "anomaly_rate": 0.2,
    }
    response = client.post("/api/v1/datasets/generate", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "API Test Dataset"
    assert data["n_cases"] == 40
    dataset_id = data["dataset_id"]

    # List datasets
    list_resp = client.get("/api/v1/datasets")
    assert list_resp.status_code == 200
    assert any(d["dataset_id"] == dataset_id for d in list_resp.json())

    # Get dataset cases
    cases_resp = client.get(f"/api/v1/datasets/{dataset_id}/cases?page=1&page_size=10")
    assert cases_resp.status_code == 200
    c_data = cases_resp.json()
    assert len(c_data["items"]) == 10
    assert c_data["pagination"]["total_items"] == 40

    first_pk = c_data["items"][0]["case_pk"]
    # Get single case
    case_detail_resp = client.get(f"/api/v1/cases/{first_pk}")
    assert case_detail_resp.status_code == 200
    assert len(case_detail_resp.json()["events"]) >= 1


def test_upload_dataset_endpoint(client: TestClient):
    csv_content = b"case_id,activity,timestamp\nC1,OrderCreated,2026-01-01T00:00:00Z\nC1,OrderPacked,2026-01-01T01:00:00Z\n"
    files = {"events_file": ("events.csv", io.BytesIO(csv_content), "text/csv")}
    data = {"workflow_id": 1, "name": "Uploaded Test Log"}

    response = client.post("/api/v1/datasets/upload", data=data, files=files)
    assert response.status_code == 201
    resp_data = response.json()
    assert resp_data["name"] == "Uploaded Test Log"
    assert resp_data["n_cases"] == 1


def test_train_and_score_ml_model(client: TestClient):
    # First generate a small dataset to train on
    gen_payload = {
        "workflow_id": 1,
        "name": "ML Train Dataset",
        "seed": 99,
        "n_train": 30,
        "n_val": 10,
        "n_test": 10,
        "anomaly_rate": 0.1,
    }
    gen_resp = client.post("/api/v1/datasets/generate", json=gen_payload)
    ds_id = gen_resp.json()["dataset_id"]

    # Train Isolation Forest
    train_payload = {
        "dataset_id": ds_id,
        "detector": "isolation_forest",
        "params": {"n_estimators": 50},
        "seed": 42,
        "target_fpr": 0.05,
    }
    train_resp = client.post("/api/v1/ml/train", json=train_payload)
    assert train_resp.status_code == 201
    m_data = train_resp.json()
    assert m_data["detector"] == "isolation_forest"
    model_run_id = m_data["model_run_id"]

    # List models
    models_resp = client.get(f"/api/v1/ml/models?dataset_id={ds_id}")
    assert models_resp.status_code == 200
    assert any(m["model_run_id"] == model_run_id for m in models_resp.json())

    # Score dataset test split
    score_payload = {
        "dataset_id": ds_id,
        "model_run_id": model_run_id,
        "split": "test",
    }
    score_resp = client.post("/api/v1/ml/score", json=score_payload)
    assert score_resp.status_code == 200
    assert score_resp.json()["n_scored"] == 10

    # Model metrics
    metrics_resp = client.get(f"/api/v1/ml/models/{model_run_id}/metrics")
    assert metrics_resp.status_code == 200
    metrics_data = metrics_resp.json()
    assert len(metrics_data["roc_points"]) >= 1
    assert "bins" in metrics_data["score_histogram"]
