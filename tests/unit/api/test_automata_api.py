"""Unit tests for automata formal operations endpoints."""

from fastapi.testclient import TestClient


def test_validate_valid_trace(client: TestClient):
    payload = {
        "workflow_id": 1,
        "case_id": "case-valid-1",
        "activities": [
            "OrderCreated",
            "PaymentInitiated",
            "PaymentAuthorized",
            "OrderPacked",
            "OrderShipped",
            "OrderDelivered",
            "OrderClosed",
        ],
    }
    response = client.post("/api/v1/automata/validate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["verdict"] == "VALID_COMPLETE"
    assert data["fail_index"] is None
    assert len(data["explanation"]) >= 1

    # Also test valid prefix in progress (without OrderClosed)
    prefix_payload = {
        "workflow_id": 1,
        "case_id": "case-prefix-1",
        "activities": [
            "OrderCreated",
            "PaymentInitiated",
            "PaymentAuthorized",
        ],
    }
    p_resp = client.post("/api/v1/automata/validate", json=prefix_payload)
    assert p_resp.status_code == 200
    assert p_resp.json()["verdict"] == "VALID_PREFIX"


def test_validate_invalid_trace(client: TestClient):
    payload = {
        "workflow_id": 1,
        "case_id": "case-invalid-1",
        "activities": [
            "OrderCreated",
            "OrderShipped",  # Illegal before payment
        ],
    }
    response = client.post("/api/v1/automata/validate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["verdict"] == "INVALID"
    assert data["fail_index"] == 1
    assert data["fail_event"] == "OrderShipped"


def test_nfa_to_dfa_subset_construction(client: TestClient):
    payload = {"use_default_retry": True}
    response = client.post("/api/v1/automata/nfa-to-dfa", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data["step_table"]) >= 4
    assert len(data["states"]) >= 4
    assert len(data["accepting_states"]) >= 1


def test_minimize_dfa_endpoint(client: TestClient):
    payload = {"workflow_id": 1}
    response = client.post("/api/v1/automata/minimize", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data["states"]) == 12  # Moore minimized merges {S1, S3} and {S8, S11}
    assert len(data["merged_partition"]) >= 1


def test_reachability_analysis_endpoint(client: TestClient):
    response = client.get("/api/v1/automata/1/reachability")
    assert response.status_code == 200
    data = response.json()
    assert "S0" in data["reachable_states"]
    assert "S_dead" in data["dead_states"]


def test_equivalence_check_endpoint(client: TestClient):
    # Automaton 1 (DFA) and Automaton 2 (MIN_DFA) accept the exact same language
    payload = {"automaton_id_1": 1, "automaton_id_2": 2}
    response = client.post("/api/v1/automata/equivalence", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["equivalent"] is True
    assert data["counterexample"] is None
