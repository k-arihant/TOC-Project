"""Unit tests for health and workflows API endpoints."""

from fastapi.testclient import TestClient


def test_health_endpoint(client: TestClient):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["db_connected"] is True
    assert data["version"] == "1.0.0"


def test_list_workflows(client: TestClient):
    response = client.get("/api/v1/workflows")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    wf = data[0]
    assert wf["name"] == "Online Order & Payment Lifecycle"
    assert wf["event_count"] == 11
    assert wf["automaton_count"] >= 3


def test_get_workflow_automaton_dfa(client: TestClient):
    response = client.get("/api/v1/workflows/1/automaton?kind=DFA")
    assert response.status_code == 200
    data = response.json()
    assert data["kind"] == "DFA"
    assert len(data["states"]) == 14
    assert len(data["transitions"]) == 154
    assert "digraph Automaton" in data["dot"]


def test_get_workflow_automaton_not_found(client: TestClient):
    response = client.get("/api/v1/workflows/999/automaton?kind=DFA")
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "WORKFLOW_NOT_FOUND"
