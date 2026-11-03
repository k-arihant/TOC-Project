import numpy as np

from src.common.types import Factor


def compute_feature_deviations(
    feature_vector: np.ndarray,
    feature_names: list[str],
    train_sorted_features: np.ndarray | None,
    train_medians: np.ndarray | None,
    top_k: int = 3,
) -> list[Factor]:
    """
    Compute descriptive deviation summary for an event trace feature vector relative
    to normal training distribution, per Doc 05 §5.4.

    For each feature, its percentile in the training distribution is computed;
    the top K features by distance from the median percentile (0.50) are returned
    as Factor objects.

    Args:
        feature_vector: 1D numpy array of shape (n_features,).
        feature_names: List of feature names.
        train_sorted_features: Pre-sorted training feature columns of shape (n_train, n_features).
        train_medians: Pre-computed training feature medians of shape (n_features,).
        top_k: Number of top deviating factors to return (default: 3).

    Returns:
        list[Factor]: Top K deviating factors.
    """
    n_features = len(feature_vector)
    if train_sorted_features is None or len(train_sorted_features) == 0:
        return []

    n_train = len(train_sorted_features)
    deviations: list[tuple[float, int, float, float]] = []  # (abs_dev, feat_idx, pct, median)

    for j in range(n_features):
        x_val = feature_vector[j]
        sorted_col = train_sorted_features[:, j]
        # Percentile rank in training data
        rank = np.searchsorted(sorted_col, x_val, side="right") / float(n_train)
        pct = float(np.clip(rank, 0.0, 1.0))
        abs_dev = abs(pct - 0.5)

        med = float(train_medians[j]) if train_medians is not None else float(np.median(sorted_col))
        deviations.append((abs_dev, j, pct, med))

    # Sort descending by distance from median percentile
    deviations.sort(key=lambda item: item[0], reverse=True)

    factors: list[Factor] = []
    for abs_dev, j, pct, med in deviations[:top_k]:
        feat_name = feature_names[j]
        val = float(feature_vector[j])
        pct_int = int(round(pct * 100))
        note = f"{feat_name}={val:.2f} (training median={med:.2f}, {pct_int}th percentile)"
        factors.append(
            Factor(
                name=feat_name,
                value=val,
                reference=med,
                note=note,
            )
        )

    return factors
