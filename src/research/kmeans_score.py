import pickle
from collections.abc import Sequence
from typing import Any

import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from src.common.types import DetectorScore, Factor, Trace
from src.workflow_ml.features import extract
from src.workflow_ml.thresholds import calibrate_threshold, compute_ecdf_ranks


class KMeansDetector:
    """
    Clustering-based anomaly detector using K-Means distance to nearest centroid,
    conforming to the AnomalyDetector protocol.

    Conventions per Doc 05 §3.3:
    - Standardize features with StandardScaler (fitted on train only)
    - raw_score = Euclidean distance to nearest cluster centroid (higher = more anomalous)
    - norm_score = ECDF rank vs training scores in [0, 1]
    - threshold is calibrated on validation negatives for target FPR
    - Factors: top 3 most deviating standardized features
    """

    def __init__(
        self,
        n_clusters: int = 5,
        random_state: int = 42,
    ) -> None:
        self.name: str = "kmeans"
        self.n_clusters = n_clusters
        self.random_state = random_state

        self.threshold: float = 0.95
        self.feature_names: list[str] = []
        self.scaler: StandardScaler | None = None
        self.kmeans: KMeans | None = None
        self.train_scores_sorted: np.ndarray | None = None
        self.train_means: np.ndarray | None = None
        self.train_scales: np.ndarray | None = None

    def _compute_centroid_distances(self, X_scaled: np.ndarray) -> np.ndarray:
        if self.kmeans is None:
            raise RuntimeError("KMeans model is not fitted.")
        centroids = self.kmeans.cluster_centers_  # (k, d)
        # Compute distances to all centroids: shape (N, k)
        # ||x - c||_2 = sqrt(sum((x - c)^2))
        diff = X_scaled[:, np.newaxis, :] - centroids[np.newaxis, :, :]  # (N, k, d)
        dist_sq = np.sum(diff**2, axis=2)  # (N, k)
        min_dist = np.sqrt(np.min(dist_sq, axis=1))  # (N,)
        return min_dist

    def fit(self, traces: Sequence[Trace]) -> None:
        """
        Fit StandardScaler and KMeans on normal-only training traces.

        Args:
            traces: Sequence of normal / valid_variation Trace objects.
        """
        if not traces:
            raise ValueError("Cannot fit KMeansDetector on empty trace sequence.")

        X, feat_names = extract(traces)
        self.feature_names = feat_names

        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        self.train_means = self.scaler.mean_
        self.train_scales = self.scaler.scale_

        k = min(self.n_clusters, len(traces))
        self.kmeans = KMeans(
            n_clusters=k,
            random_state=self.random_state,
            n_init="auto",
        )
        self.kmeans.fit(X_scaled)

        raw_train = self._compute_centroid_distances(X_scaled)
        self.train_scores_sorted = np.sort(raw_train)

    def calibrate(self, traces: Sequence[Trace], target_fpr: float = 0.05) -> None:
        """
        Calibrate decision threshold on validation normal traces.

        Args:
            traces: Sequence of normal / valid_variation validation traces.
            target_fpr: Target false positive rate (default: 0.05).
        """
        if self.kmeans is None or self.scaler is None or self.train_scores_sorted is None:
            raise RuntimeError("Cannot calibrate an unfitted KMeansDetector.")

        if not traces:
            self.threshold = 0.95
            return

        X_val, _ = extract(traces)
        X_val_scaled = self.scaler.transform(X_val)
        raw_val = self._compute_centroid_distances(X_val_scaled)
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
        if self.kmeans is None or self.scaler is None or self.train_scores_sorted is None:
            raise RuntimeError("Cannot score with an unfitted KMeansDetector.")

        if not traces:
            return []

        X, _ = extract(traces)
        X_scaled = self.scaler.transform(X)
        raw_scores = self._compute_centroid_distances(X_scaled)
        norm_scores = compute_ecdf_ranks(self.train_scores_sorted, raw_scores)

        results: list[DetectorScore] = []
        for i, trace in enumerate(traces):
            raw = float(raw_scores[i])
            norm = float(norm_scores[i])
            is_ano = bool(norm >= self.threshold)

            # Factors: top 3 features by absolute z-score
            z_scores = np.abs(X_scaled[i])
            top_indices = np.argsort(z_scores)[::-1][:3]

            factors: list[Factor] = []
            for idx in top_indices:
                feat_name = self.feature_names[idx]
                val = float(X[i, idx])
                mean_ref = float(self.train_means[idx]) if self.train_means is not None else 0.0
                z_val = float(z_scores[idx])
                factors.append(
                    Factor(
                        name=feat_name,
                        value=val,
                        reference=mean_ref,
                        note=f"{feat_name}={val:.2f} ({z_val:.2f} std devs from training mean {mean_ref:.2f})",
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
            "n_clusters": self.n_clusters,
            "random_state": self.random_state,
            "threshold": self.threshold,
            "feature_names": self.feature_names,
            "scaler": self.scaler,
            "kmeans": self.kmeans,
            "train_scores_sorted": self.train_scores_sorted,
            "train_means": self.train_means,
            "train_scales": self.train_scales,
        }
        return pickle.dumps(state)

    @classmethod
    def from_bytes(cls, b: bytes) -> "KMeansDetector":
        """Deserialize detector from bytes."""
        state = pickle.loads(b)
        detector = cls(
            n_clusters=state["n_clusters"],
            random_state=state["random_state"],
        )
        detector.name = state["name"]
        detector.threshold = state["threshold"]
        detector.feature_names = state["feature_names"]
        detector.scaler = state["scaler"]
        detector.kmeans = state["kmeans"]
        detector.train_scores_sorted = state["train_scores_sorted"]
        detector.train_means = state["train_means"]
        detector.train_scales = state["train_scales"]
        return detector
