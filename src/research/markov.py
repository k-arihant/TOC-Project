import math
import pickle
from collections import Counter
from collections.abc import Sequence
from typing import Any

import numpy as np

from src.common.types import DetectorScore, Factor, Trace
from src.workflow_ml.features import CANONICAL_ALPHABET
from src.workflow_ml.thresholds import calibrate_threshold, compute_ecdf_ranks

START_TOKEN = "<s>"
END_TOKEN = "</s>"


class MarkovDetector:
    """
    First-order transition Markov sequence detector with Laplace smoothing,
    conforming to the AnomalyDetector protocol.

    Conventions per Doc 05 §3.2:
    - First-order chain over events with <s> and </s> tokens
    - Laplace smoothing with parameter alpha (default: 1.0)
    - P(v | u) estimated from train traces
    - Scoring modes: 'mean_nll' (mean negative log-likelihood) or 'total_nll'
    - Factors: top 3 transitions with lowest probability
    - Higher score = more anomalous
    """

    def __init__(
        self,
        alpha: float = 1.0,
        scoring_mode: str = "mean_nll",
    ) -> None:
        if scoring_mode not in ("mean_nll", "total_nll"):
            raise ValueError(
                f"Invalid scoring_mode '{scoring_mode}'. Must be 'mean_nll' or 'total_nll'."
            )

        self.name: str = "markov"
        self.alpha = float(alpha)
        self.scoring_mode = scoring_mode

        self.threshold: float = 0.95
        self.transition_probs: dict[str, dict[str, float]] = {}
        self.train_scores_sorted: np.ndarray | None = None
        self.symbols: list[str] = list(CANONICAL_ALPHABET)

    def _get_transitions(self, activities: list[str]) -> list[tuple[str, str]]:
        if not activities:
            return [(START_TOKEN, END_TOKEN)]
        transitions = [(START_TOKEN, activities[0])]
        for i in range(len(activities) - 1):
            transitions.append((activities[i], activities[i + 1]))
        transitions.append((activities[-1], END_TOKEN))
        return transitions

    def fit(self, traces: Sequence[Trace]) -> None:
        """
        Fit Markov model on normal-only training traces with Laplace smoothing.

        Args:
            traces: Sequence of normal / valid_variation Trace objects.
        """
        if not traces:
            raise ValueError("Cannot fit MarkovDetector on empty trace sequence.")

        # Gather transition counts
        counts: dict[str, Counter] = {}
        all_from_states = [START_TOKEN] + self.symbols
        all_to_states = self.symbols + [END_TOKEN]

        for s in all_from_states:
            counts[s] = Counter()

        for trace in traces:
            activities = [e.activity for e in trace.events]
            transitions = self._get_transitions(activities)
            for u, v in transitions:
                if u not in counts:
                    counts[u] = Counter()
                counts[u][v] += 1

        # Compute smoothed transition probabilities
        # V_to has len(all_to_states) possible outcomes
        v_to_size = len(all_to_states)
        self.transition_probs = {}

        for u, ctr in counts.items():
            total_count = sum(ctr.values())
            denom = total_count + self.alpha * v_to_size
            self.transition_probs[u] = {}
            for v in all_to_states:
                c = ctr.get(v, 0)
                prob = (c + self.alpha) / denom
                self.transition_probs[u][v] = prob

        # Compute raw scores for training data
        raw_train = [self._score_single(t)[0] for t in traces]
        self.train_scores_sorted = np.sort(np.asarray(raw_train, dtype=np.float64))

    def _transition_prob(self, u: str, v: str) -> float:
        all_to_states = self.symbols + [END_TOKEN]
        v_to_size = len(all_to_states)

        if u in self.transition_probs:
            if v in self.transition_probs[u]:
                return self.transition_probs[u][v]
            # Unseen destination symbol
            denom = sum(self.transition_probs[u].values()) + self.alpha * (v_to_size + 1)
            return self.alpha / denom
        # Unseen source symbol
        return 1.0 / float(v_to_size)

    def _score_single(self, trace: Trace) -> tuple[float, list[tuple[str, str, float]]]:
        activities = [e.activity for e in trace.events]
        transitions = self._get_transitions(activities)

        transition_info: list[tuple[str, str, float]] = []
        nlls: list[float] = []

        for u, v in transitions:
            prob = self._transition_prob(u, v)
            prob = max(1e-12, min(1.0, prob))
            nll = -math.log(prob)
            nlls.append(nll)
            transition_info.append((u, v, prob))

        if not nlls:
            return 0.0, []

        if self.scoring_mode == "mean_nll":
            raw_score = float(np.mean(nlls))
        else:  # total_nll
            raw_score = float(np.sum(nlls))

        return raw_score, transition_info

    def calibrate(self, traces: Sequence[Trace], target_fpr: float = 0.05) -> None:
        """
        Calibrate decision threshold on validation normal traces.

        Args:
            traces: Sequence of normal / valid_variation validation traces.
            target_fpr: Target false positive rate (default: 0.05).
        """
        if self.train_scores_sorted is None:
            raise RuntimeError("Cannot calibrate an unfitted MarkovDetector.")

        if not traces:
            self.threshold = 0.95
            return

        raw_val = np.asarray([self._score_single(t)[0] for t in traces], dtype=np.float64)
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
        if self.train_scores_sorted is None:
            raise RuntimeError("Cannot score with an unfitted MarkovDetector.")

        if not traces:
            return []

        raw_scores_list: list[float] = []
        all_trans_info: list[list[tuple[str, str, float]]] = []

        for t in traces:
            raw, trans_info = self._score_single(t)
            raw_scores_list.append(raw)
            all_trans_info.append(trans_info)

        raw_arr = np.asarray(raw_scores_list, dtype=np.float64)
        norm_scores = compute_ecdf_ranks(self.train_scores_sorted, raw_arr)

        results: list[DetectorScore] = []
        for i, trace in enumerate(traces):
            raw = float(raw_arr[i])
            norm = float(norm_scores[i])
            is_ano = bool(norm >= self.threshold)

            # Factors: top 3 lowest probability transitions
            trans_info = all_trans_info[i]
            sorted_trans = sorted(trans_info, key=lambda item: item[2])
            factors: list[Factor] = []
            for u, v, p in sorted_trans[:3]:
                factors.append(
                    Factor(
                        name=f"{u}->{v}",
                        value=float(p),
                        reference=0.5,  # Reference baseline
                        note=f"Transition '{u} -> {v}' has low probability {p:.4f} in normal data",
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
            "alpha": self.alpha,
            "scoring_mode": self.scoring_mode,
            "threshold": self.threshold,
            "transition_probs": self.transition_probs,
            "train_scores_sorted": self.train_scores_sorted,
            "symbols": self.symbols,
        }
        return pickle.dumps(state)

    @classmethod
    def from_bytes(cls, b: bytes) -> "MarkovDetector":
        """Deserialize detector from bytes."""
        state = pickle.loads(b)
        detector = cls(
            alpha=state["alpha"],
            scoring_mode=state["scoring_mode"],
        )
        detector.name = state["name"]
        detector.threshold = state["threshold"]
        detector.transition_probs = state["transition_probs"]
        detector.train_scores_sorted = state["train_scores_sorted"]
        detector.symbols = state["symbols"]
        return detector
