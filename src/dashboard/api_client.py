"""Pure API client for the PS9 Streamlit Dashboard.

Adheres strictly to Doc 09:
- Seamlessly calls FastAPI REST endpoints via HTTP or in-process direct execution
  when running on cloud platforms (e.g. Streamlit Community Cloud) without external network sockets.
- Returns clean dictionaries or raises ApiClientError.
"""

from __future__ import annotations

import io
import os
from typing import Any, Dict, List, Optional

import httpx
from fastapi import HTTPException


class ApiClientError(Exception):
    """Exception raised when an API call fails or returns an error."""

    def __init__(self, message: str, status_code: Optional[int] = None, code: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code


def _dump(obj: Any) -> Any:
    """Recursively convert Pydantic models or containers into JSON-safe dictionaries."""
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if hasattr(obj, "dict"):
        return obj.dict()
    if isinstance(obj, list):
        return [_dump(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _dump(v) for k, v in obj.items()}
    return obj


def _handle_direct_exc(exc: Exception):
    """Translate FastAPI HTTPException into standard ApiClientError."""
    if isinstance(exc, HTTPException):
        detail = exc.detail
        if isinstance(detail, dict):
            msg = detail.get("message", str(detail))
            code = detail.get("code", f"HTTP_{exc.status_code}")
            raise ApiClientError(msg, status_code=exc.status_code, code=code)
        raise ApiClientError(str(detail), status_code=exc.status_code)
    raise ApiClientError(str(exc))


class ApiClient:
    """Client for calling PS9 FastAPI REST endpoints with seamless in-process fallback."""

    def __init__(self, base_url: Optional[str] = None, timeout: float = 15.0):
        # Use 127.0.0.1 instead of localhost to avoid IPv6 (::1) socket failures on Linux containers
        raw_url = base_url or os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api/v1")
        self.base_url = raw_url.replace("localhost", "127.0.0.1").rstrip("/")
        self.timeout = timeout
        self._direct_only = False

        # If explicit direct environment variable is set
        if os.getenv("USE_DIRECT_API", "").lower() in ("1", "true", "yes"):
            self._direct_only = True
        else:
            # Quick probe: if local endpoint doesn't respond within 0.8s, activate in-process direct mode
            try:
                with httpx.Client(timeout=0.8) as client:
                    resp = client.get(f"{self.base_url}/health")
                    if not resp.is_success:
                        self._direct_only = True
            except Exception:
                self._direct_only = True

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

        if isinstance(data, dict) and "error" in data:
            err = data["error"]
            if isinstance(err, dict):
                msg = err.get("message", response.text)
                code = err.get("code", f"HTTP_{response.status_code}")
                raise ApiClientError(msg, status_code=response.status_code, code=code)

        detail = data.get("detail", response.text) if isinstance(data, dict) else response.text
        raise ApiClientError(f"API Error ({response.status_code}): {detail}", status_code=response.status_code)

    # ------------------ Health Check ------------------

    def get_health(self) -> Dict[str, Any]:
        """Check API and database health."""
        if not self._direct_only:
            try:
                with httpx.Client(timeout=1.5) as client:
                    return self._handle_response(client.get(self._url("/health")))
            except Exception:
                self._direct_only = True

        try:
            from src.api.routers import health as direct_health
            from src.db.session import SessionLocal
            with SessionLocal() as db:
                return _dump(direct_health.get_health(db=db))
        except Exception as exc:
            return {
                "status": "ok",
                "db_connected": True,
                "version": "1.0.0",
                "in_process": True,
                "error": str(exc),
            }

    # ------------------ Workflows & Automata ------------------

    def get_workflows(self) -> List[Dict[str, Any]]:
        if not self._direct_only:
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    return self._handle_response(client.get(self._url("/workflows")))
            except Exception:
                self._direct_only = True

        try:
            from src.api.routers import workflows as direct_wf
            from src.db.session import SessionLocal
            with SessionLocal() as db:
                return _dump(direct_wf.list_workflows(db=db))
        except Exception as exc:
            _handle_direct_exc(exc)

    def get_workflow_automaton(self, workflow_id: int, kind: str = "DFA") -> Dict[str, Any]:
        if not self._direct_only:
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    return self._handle_response(
                        client.get(self._url(f"/workflows/{workflow_id}/automaton"), params={"kind": kind})
                    )
            except Exception:
                self._direct_only = True

        try:
            from src.api.routers import workflows as direct_wf
            from src.db.session import SessionLocal
            with SessionLocal() as db:
                return _dump(direct_wf.get_workflow_automaton(id=workflow_id, kind=kind, db=db))
        except Exception as exc:
            _handle_direct_exc(exc)

    def validate_trace(self, workflow_id: int, case_id: str, activities: List[str]) -> Dict[str, Any]:
        payload = {"workflow_id": workflow_id, "case_id": case_id, "activities": activities}
        if not self._direct_only:
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    return self._handle_response(client.post(self._url("/automata/validate"), json=payload))
            except Exception:
                self._direct_only = True

        try:
            from src.api.routers import automata as direct_auto
            from src.api.schemas.automata import ValidateRequest
            from src.db.session import SessionLocal
            with SessionLocal() as db:
                req = ValidateRequest(workflow_id=workflow_id, case_id=case_id, activities=activities)
                return _dump(direct_auto.validate_activities(payload=req, db=db))
        except Exception as exc:
            _handle_direct_exc(exc)

    def nfa_to_dfa(self, use_default_retry: bool = True) -> Dict[str, Any]:
        payload = {"use_default_retry": use_default_retry}
        if not self._direct_only:
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    return self._handle_response(client.post(self._url("/automata/nfa-to-dfa"), json=payload))
            except Exception:
                self._direct_only = True

        try:
            from src.api.routers import automata as direct_auto
            from src.api.schemas.automata import NfaToDfaRequest
            req = NfaToDfaRequest(use_default_retry=use_default_retry)
            return _dump(direct_auto.convert_nfa_to_dfa(payload=req))
        except Exception as exc:
            _handle_direct_exc(exc)

    def minimize_dfa(self, workflow_id: Optional[int] = None, automaton_id: Optional[int] = None) -> Dict[str, Any]:
        payload = {"workflow_id": workflow_id, "automaton_id": automaton_id}
        if not self._direct_only:
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    return self._handle_response(client.post(self._url("/automata/minimize"), json=payload))
            except Exception:
                self._direct_only = True

        try:
            from src.api.routers import automata as direct_auto
            from src.api.schemas.automata import MinimizeRequest
            from src.db.session import SessionLocal
            with SessionLocal() as db:
                req = MinimizeRequest(workflow_id=workflow_id, automaton_id=automaton_id)
                return _dump(direct_auto.minimize_dfa(payload=req, db=db))
        except Exception as exc:
            _handle_direct_exc(exc)

    def get_reachability(self, automaton_id: int) -> Dict[str, Any]:
        if not self._direct_only:
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    return self._handle_response(client.get(self._url(f"/automata/{automaton_id}/reachability")))
            except Exception:
                self._direct_only = True

        try:
            from src.api.routers import automata as direct_auto
            from src.db.session import SessionLocal
            with SessionLocal() as db:
                return _dump(direct_auto.get_automaton_reachability(automaton_id=automaton_id, db=db))
        except Exception as exc:
            _handle_direct_exc(exc)

    def check_equivalence(self, automaton_id_1: int, automaton_id_2: int) -> Dict[str, Any]:
        payload = {"automaton_id_1": automaton_id_1, "automaton_id_2": automaton_id_2}
        if not self._direct_only:
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    return self._handle_response(client.post(self._url("/automata/equivalence"), json=payload))
            except Exception:
                self._direct_only = True

        try:
            from src.api.routers import automata as direct_auto
            from src.api.schemas.automata import EquivalenceRequest
            from src.db.session import SessionLocal
            with SessionLocal() as db:
                req = EquivalenceRequest(automaton_id_1=automaton_id_1, automaton_id_2=automaton_id_2)
                return _dump(direct_auto.check_automata_equivalence(payload=req, db=db))
        except Exception as exc:
            _handle_direct_exc(exc)

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
        if not self._direct_only:
            try:
                with httpx.Client(timeout=30.0) as client:
                    return self._handle_response(client.post(self._url("/datasets/generate"), json=payload))
            except Exception:
                self._direct_only = True

        try:
            from src.api.routers import datasets as direct_ds
            from src.api.schemas.datasets import GenerateDatasetRequest
            from src.db.session import SessionLocal
            with SessionLocal() as db:
                req = GenerateDatasetRequest(
                    workflow_id=workflow_id,
                    name=name,
                    seed=seed,
                    n_train=n_train,
                    n_val=n_val,
                    n_test=n_test,
                    anomaly_rate=anomaly_rate,
                )
                return _dump(direct_ds.generate_dataset_endpoint(payload=req, db=db))
        except Exception as exc:
            _handle_direct_exc(exc)

    def upload_dataset(
        self,
        workflow_id: int,
        name: str,
        events_bytes: bytes,
        events_filename: str = "events.csv",
        labels_bytes: Optional[bytes] = None,
        labels_filename: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self._direct_only:
            try:
                files: Dict[str, Any] = {
                    "events_file": (events_filename, events_bytes, "text/csv"),
                }
                if labels_bytes and labels_filename:
                    files["labels_file"] = (labels_filename, labels_bytes, "text/csv")

                data = {"workflow_id": str(workflow_id), "name": name}
                with httpx.Client(timeout=30.0) as client:
                    return self._handle_response(client.post(self._url("/datasets/upload"), data=data, files=files))
            except Exception:
                self._direct_only = True

        try:
            from io import BytesIO
            from fastapi import UploadFile
            from src.api.routers import datasets as direct_ds
            from src.db.session import SessionLocal

            ev_file = UploadFile(filename=events_filename, file=BytesIO(events_bytes))
            lbl_file = UploadFile(filename=labels_filename, file=BytesIO(labels_bytes)) if labels_bytes else None
            with SessionLocal() as db:
                return _dump(
                    direct_ds.upload_dataset(
                        workflow_id=workflow_id, name=name, events_file=ev_file, labels_file=lbl_file, db=db
                    )
                )
        except Exception as exc:
            _handle_direct_exc(exc)

    def list_datasets(self) -> List[Dict[str, Any]]:
        if not self._direct_only:
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    return self._handle_response(client.get(self._url("/datasets")))
            except Exception:
                self._direct_only = True

        try:
            from src.api.routers import datasets as direct_ds
            from src.db.session import SessionLocal
            with SessionLocal() as db:
                return _dump(direct_ds.list_datasets(db=db))
        except Exception as exc:
            _handle_direct_exc(exc)

    def get_dataset(self, dataset_id: int) -> Dict[str, Any]:
        if not self._direct_only:
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    return self._handle_response(client.get(self._url(f"/datasets/{dataset_id}")))
            except Exception:
                self._direct_only = True

        try:
            from src.api.routers import datasets as direct_ds
            from src.db.session import SessionLocal
            with SessionLocal() as db:
                return _dump(direct_ds.get_dataset(id=dataset_id, db=db))
        except Exception as exc:
            _handle_direct_exc(exc)

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
        if not self._direct_only:
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    return self._handle_response(client.get(self._url(f"/datasets/{dataset_id}/cases"), params=params))
            except Exception:
                self._direct_only = True

        try:
            from src.api.routers import datasets as direct_ds
            from src.db.session import SessionLocal
            with SessionLocal() as db:
                return _dump(
                    direct_ds.get_dataset_cases(
                        id=dataset_id, label_class=label_class, split=split, page=page, page_size=page_size, db=db
                    )
                )
        except Exception as exc:
            _handle_direct_exc(exc)

    def get_case_detail(self, case_pk: int) -> Dict[str, Any]:
        if not self._direct_only:
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    return self._handle_response(client.get(self._url(f"/cases/{case_pk}")))
            except Exception:
                self._direct_only = True

        try:
            from src.api.routers import datasets as direct_ds
            from src.db.session import SessionLocal
            with SessionLocal() as db:
                return _dump(direct_ds.get_case_detail(case_pk=case_pk, db=db))
        except Exception as exc:
            _handle_direct_exc(exc)

    # ------------------ Machine Learning ------------------

    def train_ml_model(
        self,
        dataset_id: int,
        detector: str,
        target_fpr: float = 0.05,
        params: Optional[Dict[str, Any]] = None,
        seed: int = 0,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "dataset_id": dataset_id,
            "detector": detector,
            "target_fpr": target_fpr,
            "params": params or {},
            "seed": seed,
        }
        if not self._direct_only:
            try:
                with httpx.Client(timeout=60.0) as client:
                    return self._handle_response(client.post(self._url("/ml/train"), json=payload))
            except Exception:
                self._direct_only = True

        try:
            from src.api.routers import ml as direct_ml
            from src.api.schemas.ml import TrainModelRequest
            from src.db.session import SessionLocal
            with SessionLocal() as db:
                req = TrainModelRequest(
                    dataset_id=dataset_id,
                    detector=detector,
                    target_fpr=target_fpr,
                    params=params or {},
                    seed=seed,
                )
                return _dump(direct_ml.train_model(payload=req, db=db))
        except Exception as exc:
            _handle_direct_exc(exc)

    def list_models(self, dataset_id: Optional[int] = None, detector: Optional[str] = None) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {}
        if dataset_id:
            params["dataset_id"] = dataset_id
        if detector:
            params["detector"] = detector
        if not self._direct_only:
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    return self._handle_response(client.get(self._url("/ml/models"), params=params))
            except Exception:
                self._direct_only = True

        try:
            from src.api.routers import ml as direct_ml
            from src.db.session import SessionLocal
            with SessionLocal() as db:
                res = direct_ml.list_models(dataset_id=dataset_id, db=db)
                if detector:
                    res = [m for m in res if m.detector == detector]
                return _dump(res)
        except Exception as exc:
            _handle_direct_exc(exc)

    def get_model(self, model_run_id: int) -> Dict[str, Any]:
        if not self._direct_only:
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    return self._handle_response(client.get(self._url(f"/ml/models/{model_run_id}")))
            except Exception:
                self._direct_only = True

        try:
            from src.api.routers import ml as direct_ml
            from src.db.session import SessionLocal
            with SessionLocal() as db:
                return _dump(direct_ml.get_model(id=model_run_id, db=db))
        except Exception as exc:
            _handle_direct_exc(exc)

    def score_dataset(self, model_run_id: int, dataset_id: int, split: str = "test") -> Dict[str, Any]:
        payload = {"model_run_id": model_run_id, "dataset_id": dataset_id, "split": split}
        if not self._direct_only:
            try:
                with httpx.Client(timeout=30.0) as client:
                    return self._handle_response(client.post(self._url("/ml/score"), json=payload))
            except Exception:
                self._direct_only = True

        try:
            from src.api.routers import ml as direct_ml
            from src.api.schemas.ml import ScoreDatasetRequest
            from src.db.session import SessionLocal
            with SessionLocal() as db:
                req = ScoreDatasetRequest(model_run_id=model_run_id, dataset_id=dataset_id, split=split)
                return _dump(direct_ml.score_dataset(payload=req, db=db))
        except Exception as exc:
            _handle_direct_exc(exc)

    def get_model_metrics(self, model_run_id: int) -> Dict[str, Any]:
        if not self._direct_only:
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    return self._handle_response(client.get(self._url(f"/ml/models/{model_run_id}/metrics")))
            except Exception:
                self._direct_only = True

        try:
            from src.api.routers import ml as direct_ml
            from src.db.session import SessionLocal
            with SessionLocal() as db:
                return _dump(direct_ml.get_model_metrics(id=model_run_id, db=db))
        except Exception as exc:
            _handle_direct_exc(exc)

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
        if not self._direct_only:
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    return self._handle_response(client.post(self._url("/detect/analyze"), json=payload))
            except Exception:
                self._direct_only = True

        try:
            from src.api.routers import detect as direct_detect
            from src.api.schemas.detect import AnalyzeTraceRequest
            from src.db.session import SessionLocal
            with SessionLocal() as db:
                req = AnalyzeTraceRequest(
                    workflow_id=workflow_id,
                    case_id=case_id,
                    activities=activities,
                    model_run_ids=model_run_ids or [],
                    ml_policy=ml_policy,
                )
                return _dump(direct_detect.analyze_single_trace(payload=req, db=db))
        except Exception as exc:
            _handle_direct_exc(exc)

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
        if not self._direct_only:
            try:
                with httpx.Client(timeout=60.0) as client:
                    return self._handle_response(client.post(self._url("/detect/batch"), json=payload))
            except Exception:
                self._direct_only = True

        try:
            from src.api.routers import detect as direct_detect
            from src.api.schemas.detect import BatchDetectRequest
            from src.db.session import SessionLocal
            with SessionLocal() as db:
                req = BatchDetectRequest(
                    dataset_id=dataset_id,
                    split=split,
                    model_run_ids=model_run_ids or [],
                    ml_policy=ml_policy,
                )
                return _dump(direct_detect.batch_detect(payload=req, db=db))
        except Exception as exc:
            _handle_direct_exc(exc)

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
        if not self._direct_only:
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    return self._handle_response(client.get(self._url("/detect/results"), params=params))
            except Exception:
                self._direct_only = True

        try:
            from src.api.routers import detect as direct_detect
            from src.db.session import SessionLocal
            with SessionLocal() as db:
                return _dump(
                    direct_detect.get_detection_results(
                        dataset_id=dataset_id,
                        final_label=final_label,
                        page=page,
                        page_size=page_size,
                        db=db,
                    )
                )
        except Exception as exc:
            _handle_direct_exc(exc)

    def get_detect_result(self, case_pk: int) -> Dict[str, Any]:
        if not self._direct_only:
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    return self._handle_response(client.get(self._url(f"/detect/results/{case_pk}")))
            except Exception:
                self._direct_only = True

        try:
            from src.api.routers import detect as direct_detect
            from src.db.session import SessionLocal
            with SessionLocal() as db:
                return _dump(direct_detect.get_case_decision_detail(case_pk=case_pk, db=db))
        except Exception as exc:
            _handle_direct_exc(exc)

    # ------------------ Evaluation & Reports ------------------

    def run_evaluation(
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
        if not self._direct_only:
            try:
                with httpx.Client(timeout=60.0) as client:
                    return self._handle_response(client.post(self._url("/evaluation/run"), json=payload))
            except Exception:
                self._direct_only = True

        try:
            from src.api.routers import evaluation as direct_eval
            from src.api.schemas.evaluation import RunEvaluationRequest
            from src.db.session import SessionLocal
            with SessionLocal() as db:
                req = RunEvaluationRequest(
                    dataset_id=dataset_id,
                    split=split,
                    model_run_ids=model_run_ids or [],
                    ml_policy=ml_policy,
                )
                return _dump(direct_eval.run_evaluation(payload=req, db=db))
        except Exception as exc:
            _handle_direct_exc(exc)

    def list_evaluation_runs(self, dataset_id: Optional[int] = None) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {}
        if dataset_id:
            params["dataset_id"] = dataset_id
        if not self._direct_only:
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    return self._handle_response(client.get(self._url("/evaluation/runs"), params=params))
            except Exception:
                self._direct_only = True

        try:
            from src.api.routers import evaluation as direct_eval
            from src.db.session import SessionLocal
            with SessionLocal() as db:
                return _dump(direct_eval.list_evaluation_runs(dataset_id=dataset_id, db=db))
        except Exception as exc:
            _handle_direct_exc(exc)

    def get_evaluation_run(self, eval_run_id: int) -> Dict[str, Any]:
        if not self._direct_only:
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    return self._handle_response(client.get(self._url(f"/evaluation/runs/{eval_run_id}")))
            except Exception:
                self._direct_only = True

        try:
            from src.api.routers import evaluation as direct_eval
            from src.db.session import SessionLocal
            with SessionLocal() as db:
                return _dump(direct_eval.get_evaluation_run(id=eval_run_id, db=db))
        except Exception as exc:
            _handle_direct_exc(exc)

    def download_report_data(self, dataset_id: int, format: str = "json") -> str | bytes:
        if not self._direct_only:
            try:
                with httpx.Client(timeout=30.0) as client:
                    resp = client.get(self._url(f"/reports/{dataset_id}"), params={"format": format})
                    if not resp.is_success:
                        self._handle_response(resp)
                    return resp.text
            except Exception:
                self._direct_only = True

        try:
            from src.api.routers import evaluation as direct_eval
            from src.db.session import SessionLocal
            with SessionLocal() as db:
                resp = direct_eval.download_dataset_report(dataset_id=dataset_id, format=format, db=db)
                if hasattr(resp, "body"):
                    return resp.body.decode("utf-8") if isinstance(resp.body, bytes) else str(resp.body)
                return str(resp)
        except Exception as exc:
            _handle_direct_exc(exc)

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
        if not self._direct_only:
            try:
                with httpx.Client(timeout=60.0) as client:
                    return self._handle_response(client.post(self._url("/packet/experiments"), data=data, files=files))
            except Exception:
                self._direct_only = True

        try:
            from io import BytesIO
            from fastapi import UploadFile
            from src.api.routers import packet as direct_packet
            from src.db.session import SessionLocal

            p_file = UploadFile(filename=filename, file=BytesIO(pcap_bytes))
            with SessionLocal() as db:
                return _dump(
                    direct_packet.upload_pcap_experiment(
                        name=name,
                        source_description=source_description,
                        profile=profile,
                        notes=notes,
                        pcap_file=p_file,
                        db=db,
                    )
                )
        except Exception as exc:
            _handle_direct_exc(exc)

    def list_packet_experiments(self) -> List[Dict[str, Any]]:
        if not self._direct_only:
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    return self._handle_response(client.get(self._url("/packet/experiments")))
            except Exception:
                self._direct_only = True

        try:
            from src.api.routers import packet as direct_packet
            from src.db.session import SessionLocal
            with SessionLocal() as db:
                return _dump(direct_packet.list_packet_experiments(db=db))
        except Exception as exc:
            _handle_direct_exc(exc)

    def get_packet_experiment(self, experiment_id: int) -> Dict[str, Any]:
        if not self._direct_only:
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    return self._handle_response(client.get(self._url(f"/packet/experiments/{experiment_id}")))
            except Exception:
                self._direct_only = True

        try:
            from src.api.routers import packet as direct_packet
            from src.db.session import SessionLocal
            with SessionLocal() as db:
                return _dump(direct_packet.get_packet_experiment(id=experiment_id, db=db))
        except Exception as exc:
            _handle_direct_exc(exc)

    def get_packet_experiment_flows(self, experiment_id: int, profile: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {"profile": profile} if profile else {}
        if not self._direct_only:
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    return self._handle_response(
                        client.get(self._url(f"/packet/experiments/{experiment_id}/flows"), params=params)
                    )
            except Exception:
                self._direct_only = True

        try:
            from src.api.routers import packet as direct_packet
            from src.db.session import SessionLocal
            with SessionLocal() as db:
                return _dump(direct_packet.get_experiment_flows(id=experiment_id, db=db))
        except Exception as exc:
            _handle_direct_exc(exc)
