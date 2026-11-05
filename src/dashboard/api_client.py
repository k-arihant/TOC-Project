"""Pure API client for the PS9 Streamlit Dashboard.

Adheres strictly to Doc 09:
- Does NOT import any internal ML, automata, or database models.
- Interacts exclusively with the FastAPI REST API via HTTP.
- Returns clean dictionaries or raises ApiClientError.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import httpx


class ApiClientError(Exception):
    """Exception raised when an API call fails or returns an error."""

    def __init__(self, message: str, status_code: Optional[int] = None, code: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code


class ApiClient:
    """Client for calling PS9 FastAPI REST endpoints."""

    def __init__(self, base_url: Optional[str] = None, timeout: float = 15.0):
        self.base_url = (base_url or os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")).rstrip("/")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        clean_path = path if path.startswith("/") else f"/{path}"
        return f"{self.base_url}{clean_path}"

    def _handle_response(self, response: httpx.Response) -> Any:
        try:
            data = response.json()
        except Exception:
            data = None

        if response.is_success:
            return data

        # Extract standard error format {"error": {"code": "...", "message": "..."}}
        if isinstance(data, dict) and "error" in data:
            err = data["error"]
            if isinstance(err, dict):
                msg = err.get("message", response.text)
                code = err.get("code", f"HTTP_{response.status_code}")
                raise ApiClientError(msg, status_code=response.status_code, code=code)

        detail = data.get("detail", response.text) if isinstance(data, dict) else response.text
        raise ApiClientError(f"API Error ({response.status_code}): {detail}", status_code=response.status_code)

    def get_health(self) -> Dict[str, Any]:
        """Check API and database health."""
        try:
            with httpx.Client(timeout=3.0) as client:
                resp = client.get(self._url("/health"))
                return self._handle_response(resp)
        except Exception as exc:
            return {
                "status": "disconnected",
                "db_connected": False,
                "version": "unknown",
                "error": str(exc),
            }

    # ------------------ Workflows & Automata ------------------

    def get_workflows(self) -> List[Dict[str, Any]]:
        with httpx.Client(timeout=self.timeout) as client:
            return self._handle_response(client.get(self._url("/workflows")))

    def get_workflow_automaton(self, workflow_id: int, kind: str = "DFA") -> Dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            return self._handle_response(
                client.get(self._url(f"/workflows/{workflow_id}/automaton"), params={"kind": kind})
            )

    def validate_trace(self, workflow_id: int, case_id: str, activities: List[str]) -> Dict[str, Any]:
        payload = {"workflow_id": workflow_id, "case_id": case_id, "activities": activities}
        with httpx.Client(timeout=self.timeout) as client:
            return self._handle_response(client.post(self._url("/automata/validate"), json=payload))

    def nfa_to_dfa(self, use_default_retry: bool = True) -> Dict[str, Any]:
        payload = {"use_default_retry": use_default_retry}
        with httpx.Client(timeout=self.timeout) as client:
            return self._handle_response(client.post(self._url("/automata/nfa-to-dfa"), json=payload))

    def minimize_dfa(self, workflow_id: Optional[int] = None, automaton_id: Optional[int] = None) -> Dict[str, Any]:
        payload = {"workflow_id": workflow_id, "automaton_id": automaton_id}
        with httpx.Client(timeout=self.timeout) as client:
            return self._handle_response(client.post(self._url("/automata/minimize"), json=payload))

    def get_reachability(self, automaton_id: int) -> Dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            return self._handle_response(client.get(self._url(f"/automata/{automaton_id}/reachability")))

    def check_equivalence(self, automaton_id_1: int, automaton_id_2: int) -> Dict[str, Any]:
        payload = {"automaton_id_1": automaton_id_1, "automaton_id_2": automaton_id_2}
        with httpx.Client(timeout=self.timeout) as client:
            return self._handle_response(client.post(self._url("/automata/equivalence"), json=payload))

    # ------------------ Datasets ------------------

    def generate_dataset(
        self,
        workflow_id: int,
        name: str,
        seed: int = 0,
        n_train: int = 600,
        n_val: int = 200,
        n_test: int = 200,
        anomaly_rate: float = 0.10,
    ) -> Dict[str, Any]:
        payload = {
            "workflow_id": workflow_id,
            "name": name,
            "seed": seed,
            "n_train": n_train,
            "n_val": n_val,
            "n_test": n_test,
            "anomaly_rate": anomaly_rate,
        }
        with httpx.Client(timeout=30.0) as client:
            return self._handle_response(client.post(self._url("/datasets/generate"), json=payload))

    def upload_dataset(
        self,
        workflow_id: int,
        name: str,
        events_bytes: bytes,
        events_filename: str = "events.csv",
        labels_bytes: Optional[bytes] = None,
        labels_filename: Optional[str] = None,
    ) -> Dict[str, Any]:
        files: Dict[str, Any] = {
            "events_file": (events_filename, events_bytes, "text/csv"),
        }
        if labels_bytes and labels_filename:
            files["labels_file"] = (labels_filename, labels_bytes, "text/csv")

        data = {"workflow_id": str(workflow_id), "name": name}
        with httpx.Client(timeout=30.0) as client:
            return self._handle_response(client.post(self._url("/datasets/upload"), data=data, files=files))

    def list_datasets(self) -> List[Dict[str, Any]]:
        with httpx.Client(timeout=self.timeout) as client:
            return self._handle_response(client.get(self._url("/datasets")))

    def get_dataset(self, dataset_id: int) -> Dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            return self._handle_response(client.get(self._url(f"/datasets/{dataset_id}")))

    def get_dataset_cases(
        self,
        dataset_id: int,
        label_class: Optional[str] = None,
        split: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"page": page, "page_size": page_size}
        if label_class:
            params["label_class"] = label_class
        if split:
            params["split"] = split
        with httpx.Client(timeout=self.timeout) as client:
            return self._handle_response(client.get(self._url(f"/datasets/{dataset_id}/cases"), params=params))

    def get_case_detail(self, case_pk: int) -> Dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            return self._handle_response(client.get(self._url(f"/cases/{case_pk}")))

    # ------------------ Machine Learning ------------------

    def train_ml_model(
        self,
        dataset_id: int,
        detector: str,
        target_fpr: float = 0.05,
        contamination: Optional[float] = None,
        hyperparameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "dataset_id": dataset_id,
            "detector": detector,
            "target_fpr": target_fpr,
            "contamination": contamination,
            "hyperparameters": hyperparameters or {},
        }
        with httpx.Client(timeout=60.0) as client:
            return self._handle_response(client.post(self._url("/ml/train"), json=payload))

    def list_models(self, dataset_id: Optional[int] = None, detector: Optional[str] = None) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {}
        if dataset_id:
            params["dataset_id"] = dataset_id
        if detector:
            params["detector"] = detector
        with httpx.Client(timeout=self.timeout) as client:
            return self._handle_response(client.get(self._url("/ml/models"), params=params))

    def get_model(self, model_run_id: int) -> Dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            return self._handle_response(client.get(self._url(f"/ml/models/{model_run_id}")))

    def score_dataset(self, model_run_id: int, dataset_id: int, split: str = "test") -> Dict[str, Any]:
        payload = {"model_run_id": model_run_id, "dataset_id": dataset_id, "split": split}
        with httpx.Client(timeout=30.0) as client:
            return self._handle_response(client.post(self._url("/ml/score"), json=payload))

    def get_model_metrics(self, model_run_id: int) -> Dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            return self._handle_response(client.get(self._url(f"/ml/models/{model_run_id}/metrics")))

    # ------------------ Hybrid Detection ------------------

    def detect_analyze(
        self,
        workflow_id: int,
        case_id: str,
        activities: List[str],
        model_run_ids: Optional[List[int]] = None,
        ml_policy: str = "any",
    ) -> Dict[str, Any]:
        payload = {
            "workflow_id": workflow_id,
            "case_id": case_id,
            "activities": activities,
            "model_run_ids": model_run_ids or [],
            "ml_policy": ml_policy,
        }
        with httpx.Client(timeout=self.timeout) as client:
            return self._handle_response(client.post(self._url("/detect/analyze"), json=payload))

    def detect_batch(
        self,
        dataset_id: int,
        split: str = "test",
        model_run_ids: Optional[List[int]] = None,
        ml_policy: str = "any",
    ) -> Dict[str, Any]:
        payload = {
            "dataset_id": dataset_id,
            "split": split,
            "model_run_ids": model_run_ids or [],
            "ml_policy": ml_policy,
        }
        with httpx.Client(timeout=60.0) as client:
            return self._handle_response(client.post(self._url("/detect/batch"), json=payload))

    def list_detect_results(
        self,
        dataset_id: Optional[int] = None,
        final_label: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"page": page, "page_size": page_size}
        if dataset_id:
            params["dataset_id"] = dataset_id
        if final_label:
            params["final_label"] = final_label
        with httpx.Client(timeout=self.timeout) as client:
            return self._handle_response(client.get(self._url("/detect/results"), params=params))

    def get_detect_result(self, case_pk: int) -> Dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            return self._handle_response(client.get(self._url(f"/detect/results/{case_pk}")))

    # ------------------ Evaluation & Reports ------------------

    def run_evaluation(
        self,
        dataset_id: int,
        split: str = "test",
        model_run_ids: Optional[List[int]] = None,
        ml_policy: str = "any",
        record_in_db: bool = True,
    ) -> Dict[str, Any]:
        payload = {
            "dataset_id": dataset_id,
            "split": split,
            "model_run_ids": model_run_ids or [],
            "ml_policy": ml_policy,
            "record_in_db": record_in_db,
        }
        with httpx.Client(timeout=60.0) as client:
            return self._handle_response(client.post(self._url("/evaluation/run"), json=payload))

    def list_evaluation_runs(self, dataset_id: Optional[int] = None) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {}
        if dataset_id:
            params["dataset_id"] = dataset_id
        with httpx.Client(timeout=self.timeout) as client:
            return self._handle_response(client.get(self._url("/evaluation/runs"), params=params))

    def get_evaluation_run(self, eval_run_id: int) -> Dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            return self._handle_response(client.get(self._url(f"/evaluation/runs/{eval_run_id}")))

    def download_report_data(self, dataset_id: int, format: str = "json") -> str | bytes:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(self._url(f"/reports/{dataset_id}"), params={"format": format})
            if not resp.is_success:
                self._handle_response(resp)
            return resp.text

    # ------------------ Packet Validation ------------------

    def upload_packet_experiment(
        self,
        name: str,
        source_description: str,
        profile: str,
        pcap_bytes: bytes,
        notes: Optional[str] = None,
        filename: str = "capture.pcap",
    ) -> Dict[str, Any]:
        files = {"pcap_file": (filename, pcap_bytes, "application/vnd.tcpdump.pcap")}
        data = {
            "name": name,
            "source_description": source_description,
            "profile": profile,
        }
        if notes:
            data["notes"] = notes
        with httpx.Client(timeout=60.0) as client:
            return self._handle_response(client.post(self._url("/packet/experiments"), data=data, files=files))

    def list_packet_experiments(self) -> List[Dict[str, Any]]:
        with httpx.Client(timeout=self.timeout) as client:
            return self._handle_response(client.get(self._url("/packet/experiments")))

    def get_packet_experiment(self, experiment_id: int) -> Dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            return self._handle_response(client.get(self._url(f"/packet/experiments/{experiment_id}")))

    def get_packet_experiment_flows(self, experiment_id: int, profile: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {"profile": profile} if profile else {}
        with httpx.Client(timeout=self.timeout) as client:
            return self._handle_response(client.get(self._url(f"/packet/experiments/{experiment_id}/flows"), params=params))
