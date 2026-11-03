from collections.abc import Sequence

import numpy as np


def compute_ecdf_ranks(train_scores: np.ndarray, query_scores: np.ndarray) -> np.ndarray:
    """
    Compute empirical cumulative distribution function (ECDF) percentile ranks
    of query_scores relative to train_scores distribution.

    Since higher raw score = more anomalous, higher ECDF rank indicates
    higher anomaly severity relative to training data.

    Returns:
        np.ndarray of shape query_scores.shape with values clipped to [0.0, 1.0].
    """
    if len(train_scores) == 0:
        return np.full_like(query_scores, 0.5, dtype=np.float64)

    train_sorted = np.sort(np.asarray(train_scores, dtype=np.float64))
    q_arr = np.asarray(query_scores, dtype=np.float64)

    # searchsorted(side='right') gives count of train_scores <= q
    ranks = np.searchsorted(train_sorted, q_arr, side="right") / float(len(train_sorted))
    return np.clip(ranks, 0.0, 1.0).astype(np.float64)


def calibrate_threshold(negative_scores: Sequence[float], target_fpr: float = 0.05) -> float:
    """
    Calibrate decision threshold tau on validation negative scores for a given target FPR.

    Per Doc 05 §4:
    tau = (1 - target_fpr)-quantile of validation cases whose class in {normal, valid_variation}.

    Args:
        negative_scores: Sequence of norm_score values for validation negatives.
        target_fpr: Target false-positive rate (default: 0.05).

    Returns:
        float: Calibrated threshold tau in [0.0, 1.0].
    """
    if len(negative_scores) == 0:
        return 0.95

    arr = np.asarray(negative_scores, dtype=np.float64)
    # 1 - target_fpr quantile (e.g. 0.95 quantile for 0.05 FPR)
    quantile_q = max(0.0, min(1.0, 1.0 - target_fpr))
    tau = float(np.quantile(arr, quantile_q, method="linear"))
    return float(np.clip(tau, 0.0, 1.0))
