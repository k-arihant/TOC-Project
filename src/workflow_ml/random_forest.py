import pickle
from collections.abc import Sequence
from typing import Any

import numpy as np
from sklearn.ensemble import RandomForestClassifier

from src.common.types import DetectorScore, Factor, Trace
from src.workflow_ml.features import extract
from src.workflow_ml.thresholds import calibrate_threshold, compute_ecdf_ranks


class RandomForestDetector:
    """
    Supervised reference model trained on injected labels, per Doc 05 §3.4.

    Safeguards & Reporting:
    - Labelled in all outputs as 'supervised reference under injected labels'
    - class_weight='balanced'
    - Probability of anomaly P(anomaly | x) used as raw_score
    - norm_score is ECDF rank vs training scores in [0, 1]
    - threshold calibrated on validation negatives
    """

    def __init__(
        self,
        n_estimators: int = 100,
        random_state: int = 42,
    ) -> None:
        self.name: str = "random_forest"
        self.n_estimators = n_estimators
        self.random_state = random_state

        self.threshold: float = 0.95
        self.feature_names: list[str] = []
        self.model: RandomForestClassifier | None = None
        self.train_scores_sorted: np.ndarray | None = None
        self.feature_importances: np.ndarray | None = None

    def fit_supervised(self, traces: Sequence[Trace], labels: Sequence[int]) -> None:
        """
        Fit supervised Random Forest classifier on train traces with binary labels
        (0 = normal / valid_variation, 1 = rule_violation / statistical_anomaly).

        Args:
            traces: Sequence of Trace objects from the train split.
            labels: Binary labels (0 or 1) for each trace.
        """
        if not traces:
            raise ValueError("Cannot fit RandomForestDetector on empty trace sequence.")

        X, feat_names = extract(traces)
        self.feature_names = feat_names

        y = np.asarray(labels, dtype=np.int64)

        # Ensure at least one positive and one negative class
        if len(np.unique(y)) < 2:
            class_weight = None
        else:
            class_weight = "balanced"

        self.model = RandomForestClassifier(
            n_estimators=self.n_estimators,
            class_weight=class_weight,
            random_state=self.random_state,
        )
        self.model.fit(X, y)
        self.feature_importances = self.model.feature_importances_

        # Anomaly probability
        if len(self.model.classes_) == 1:
            raw_train = np.zeros(len(traces), dtype=np.float64)
        else:
            raw_train = self.model.predict_proba(X)[:, 1]

        self.train_scores_sorted = np.sort(raw_train)

    def fit(self, traces: Sequence[Trace]) -> None:
        """
        Unsupervised interface compatibility: assumes all traces are normal (label 0).
        """
        labels = [0] * len(traces)
        self.fit_supervised(traces, labels)

    def calibrate(self, traces: Sequence[Trace], target_fpr: float = 0.05) -> None:
        """
        Calibrate decision threshold on validation normal traces.

        Args:
            traces: Sequence of normal / valid_variation validation traces.
            target_fpr: Target false positive rate (default: 0.05).
        """
        if self.model is None or self.train_scores_sorted is None:
            raise RuntimeError("Cannot calibrate an unfitted RandomForestDetector.")

        if not traces:
            self.threshold = 0.95
            return

        X_val, _ = extract(traces)
        if len(self.model.classes_) == 1:
            raw_val = np.zeros(len(traces), dtype=np.float64)
        else:
            raw_val = self.model.predict_proba(X_val)[:, 1]

        norm_val = compute_ecdf_ranks(self.train_scores_sorted, raw_val)
        self.threshold = calibrate_threshold(norm_val, target_fpr=target_fpr)

    def score(self, traces: Sequence[Trace]) -> list[DetectorScore]:
        """
        Compute anomaly scores for given traces.

        Args:
            traces: Sequence of Trace objects.

        Returns:
            list[DetectorScore]: Anomaly scores, calibrated threshold, and explanation factors.
        """
        if self.model is None or self.train_scores_sorted is None:
            raise RuntimeError("Cannot score with an unfitted RandomForestDetector.")

        if not traces:
            return []

        X, _ = extract(traces)
        if len(self.model.classes_) == 1:
            raw_scores = np.zeros(len(traces), dtype=np.float64)
        else:
            raw_scores = self.model.predict_proba(X)[:, 1]

        norm_scores = compute_ecdf_ranks(self.train_scores_sorted, raw_scores)

        results: list[DetectorScore] = []
        for i, trace in enumerate(traces):
            raw = float(raw_scores[i])
            norm = float(norm_scores[i])
            is_ano = bool(norm >= self.threshold)

            # Factors: top 3 most important features according to tree importances
            factors: list[Factor] = []
            if self.feature_importances is not None:
                top_indices = np.argsort(self.feature_importances)[::-1][:3]
                for idx in top_indices:
                    feat_name = self.feature_names[idx]
                    val = float(X[i, idx])
                    imp = float(self.feature_importances[idx])
                    factors.append(
                        Factor(
                            name=feat_name,
                            value=val,
                            reference=imp,
                            note=f"{feat_name}={val:.2f} (RF importance={imp:.3f})",
                        )
                    )

            results.append(
                DetectorScore(
                    case_id=trace.case_id,
                    detector=self.name,
                    raw_score=raw,
                    norm_score=norm,
                    threshold=self.threshold,
                    is_anomaly=is_ano,
                    factors=factors,
                )
            )

        return results

    def to_bytes(self) -> bytes:
        """Serialize detector state to bytes."""
        state: dict[str, Any] = {
            "name": self.name,
            "n_estimators": self.n_estimators,
            "random_state": self.random_state,
            "threshold": self.threshold,
            "feature_names": self.feature_names,
            "model": self.model,
            "train_scores_sorted": self.train_scores_sorted,
            "feature_importances": self.feature_importances,
        }
        return pickle.dumps(state)

    @classmethod
    def from_bytes(cls, b: bytes) -> "RandomForestDetector":
        """Deserialize detector from bytes."""
        state = pickle.loads(b)
        detector = cls(
            n_estimators=state["n_estimators"],
            random_state=state["random_state"],
        )
        detector.name = state["name"]
        detector.threshold = state["threshold"]
        detector.feature_names = state["feature_names"]
        detector.model = state["model"]
        detector.train_scores_sorted = state["train_scores_sorted"]
        detector.feature_importances = state["feature_importances"]
        return detector
