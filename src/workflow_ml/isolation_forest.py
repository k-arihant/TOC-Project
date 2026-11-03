import pickle
from collections.abc import Sequence
from typing import Any

import numpy as np
from sklearn.ensemble import IsolationForest

from src.common.types import DetectorScore, Trace
from src.workflow_ml.explain import compute_feature_deviations
from src.workflow_ml.features import extract
from src.workflow_ml.thresholds import calibrate_threshold, compute_ecdf_ranks


class IsolationForestDetector:
    """
    Unsupervised statistical anomaly detector using scikit-learn's Isolation Forest,
    conforming to the AnomalyDetector protocol.

    Conventions per Doc 05 §3.1:
    - raw_score = -score_samples(X) (higher = more anomalous)
    - norm_score = ECDF rank of raw_score among training scores in [0, 1]
    - threshold is calibrated on validation negatives for target FPR
    - is_anomaly = norm_score >= threshold
    """

    def __init__(
        self,
        n_estimators: int = 100,
        max_samples: int | float | str = 256,
        max_features: float = 1.0,
        random_state: int = 42,
    ) -> None:
        self.name: str = "isolation_forest"
        self.n_estimators = n_estimators
        self.max_samples = max_samples
        self.max_features = max_features
        self.random_state = random_state

        self.model: IsolationForest | None = None
        self.threshold: float = 0.95
        self.feature_names: list[str] = []
        self.train_scores_sorted: np.ndarray | None = None
        self.train_sorted_features: np.ndarray | None = None
        self.train_medians: np.ndarray | None = None

    def fit(self, traces: Sequence[Trace]) -> None:
        """
        Fit model on normal-only training data (unsupervised).

        Args:
            traces: Sequence of normal / valid_variation Trace objects.
        """
        if not traces:
            raise ValueError("Cannot fit IsolationForestDetector on empty trace sequence.")

        X, feat_names = extract(traces)
        self.feature_names = feat_names

        # Precompute training reference distributions for descriptive explanations
        self.train_sorted_features = np.sort(X, axis=0)
        self.train_medians = np.median(X, axis=0)

        # Handle case where sample count < max_samples
        max_samp: int | float | str = self.max_samples
        if isinstance(max_samp, int) and max_samp > len(traces):
            max_samp = len(traces)

        self.model = IsolationForest(
            n_estimators=self.n_estimators,
            max_samples=max_samp,
            max_features=self.max_features,
            random_state=self.random_state,
            contamination="auto",
        )
        self.model.fit(X)

        # Raw scores: -score_samples(X) (higher = more anomalous)
        raw_train = -self.model.score_samples(X)
        self.train_scores_sorted = np.sort(raw_train)

    def calibrate(self, traces: Sequence[Trace], target_fpr: float = 0.05) -> None:
        """
        Calibrate decision threshold on validation normal traces.

        Args:
            traces: Sequence of normal / valid_variation validation traces.
            target_fpr: Target false positive rate (default: 0.05).
        """
        if self.model is None or self.train_scores_sorted is None:
            raise RuntimeError("Cannot calibrate an unfitted IsolationForestDetector.")

        if not traces:
            self.threshold = 0.95
            return

        X_val, _ = extract(traces)
        raw_val = -self.model.score_samples(X_val)
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
            raise RuntimeError("Cannot score with an unfitted IsolationForestDetector.")

        if not traces:
            return []

        X, _ = extract(traces)
        raw_scores = -self.model.score_samples(X)
        norm_scores = compute_ecdf_ranks(self.train_scores_sorted, raw_scores)

        results: list[DetectorScore] = []
        for i, trace in enumerate(traces):
            raw = float(raw_scores[i])
            norm = float(norm_scores[i])
            is_ano = bool(norm >= self.threshold)

            factors = compute_feature_deviations(
                feature_vector=X[i],
                feature_names=self.feature_names,
                train_sorted_features=self.train_sorted_features,
                train_medians=self.train_medians,
                top_k=3,
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
            "max_samples": self.max_samples,
            "max_features": self.max_features,
            "random_state": self.random_state,
            "threshold": self.threshold,
            "feature_names": self.feature_names,
            "model": self.model,
            "train_scores_sorted": self.train_scores_sorted,
            "train_sorted_features": self.train_sorted_features,
            "train_medians": self.train_medians,
        }
        return pickle.dumps(state)

    @classmethod
    def from_bytes(cls, b: bytes) -> "IsolationForestDetector":
        """Deserialize detector from bytes."""
        state = pickle.loads(b)
        detector = cls(
            n_estimators=state["n_estimators"],
            max_samples=state["max_samples"],
            max_features=state["max_features"],
            random_state=state["random_state"],
        )
        detector.name = state["name"]
        detector.threshold = state["threshold"]
        detector.feature_names = state["feature_names"]
        detector.model = state["model"]
        detector.train_scores_sorted = state["train_scores_sorted"]
        detector.train_sorted_features = state["train_sorted_features"]
        detector.train_medians = state["train_medians"]
        return detector
