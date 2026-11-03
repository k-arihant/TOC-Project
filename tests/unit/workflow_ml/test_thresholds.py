import numpy as np

from src.workflow_ml.thresholds import calibrate_threshold, compute_ecdf_ranks


def test_compute_ecdf_ranks_basic():
    train_scores = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    query_scores = np.array([0.5, 1.0, 3.0, 5.0, 10.0])

    ranks = compute_ecdf_ranks(train_scores, query_scores)

    # 0.5 is less than all -> 0.0
    # 1.0 is <= 1.0 -> 1/5 = 0.2
    # 3.0 is <= 3.0 -> 3/5 = 0.6
    # 5.0 is <= 5.0 -> 5/5 = 1.0
    # 10.0 is greater than all -> 5/5 = 1.0
    assert np.isclose(ranks[0], 0.0)
    assert np.isclose(ranks[1], 0.2)
    assert np.isclose(ranks[2], 0.6)
    assert np.isclose(ranks[3], 1.0)
    assert np.isclose(ranks[4], 1.0)


def test_compute_ecdf_ranks_empty_train():
    ranks = compute_ecdf_ranks(np.array([]), np.array([1.0, 2.0]))
    assert (ranks == 0.5).all()


def test_calibrate_threshold():
    # 100 negative scores evenly distributed from 0.01 to 1.00
    neg_scores = np.linspace(0.01, 1.0, 100)
    tau = calibrate_threshold(neg_scores, target_fpr=0.05)
    # 95th percentile should be approx 0.9505
    assert 0.94 <= tau <= 0.96


def test_calibrate_threshold_empty():
    tau = calibrate_threshold([], target_fpr=0.05)
    assert tau == 0.95
