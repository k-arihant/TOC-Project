"""Tests for case-level stratified splitting and held-out anomaly isolation."""

from src.workflow_ml.injector import AnomalyInjector
from src.workflow_ml.simulator import WorkflowSimulator
from src.workflow_ml.splits import split_cases


def test_split_disjointness_and_coverage():
    """Split disjointness test (Doc 06 §9): No case_id in two splits; all cases assigned."""
    sim = WorkflowSimulator(seed=77)
    raw_cases = sim.generate_dataset(n_cases=200)
    injector = AnomalyInjector(seed=77)
    cases = injector.inject_anomalies(raw_cases)

    split_map = split_cases(cases, seed=77)

    assert len(split_map) == len(cases)

    train_ids = {cid for cid, s in split_map.items() if s == "train"}
    val_ids = {cid for cid, s in split_map.items() if s == "val"}
    test_ids = {cid for cid, s in split_map.items() if s == "test"}

    # Disjointness check
    assert train_ids.isdisjoint(val_ids)
    assert train_ids.isdisjoint(test_ids)
    assert val_ids.isdisjoint(test_ids)

    # Coverage check
    all_case_ids = {c.trace.case_id for c in cases}
    assert (train_ids | val_ids | test_ids) == all_case_ids


def test_held_out_anomaly_types_only_in_test():
    """Held-out anomaly types must strictly appear in 'test' split only (Doc 06 §6)."""
    sim = WorkflowSimulator(seed=88)
    raw_cases = sim.generate_dataset(n_cases=300)
    injector = AnomalyInjector(seed=88)
    cases = injector.inject_anomalies(raw_cases)

    split_map = split_cases(cases, seed=88)

    held_out_types = {"event_after_closed", "burst_fast"}

    for c in cases:
        cid = c.trace.case_id
        if c.anomaly_type in held_out_types:
            assert split_map[cid] == "test", (
                f"Held-out anomaly '{c.anomaly_type}' for case '{cid}' was placed in '{split_map[cid]}'!"
            )


def test_split_proportions():
    """Split proportions are approximately 60 / 20 / 20."""
    sim = WorkflowSimulator(seed=12)
    raw_cases = sim.generate_dataset(n_cases=500)
    injector = AnomalyInjector(seed=12)
    cases = injector.inject_anomalies(raw_cases)

    split_map = split_cases(cases, seed=12)
    n = len(cases)

    train_count = sum(1 for s in split_map.values() if s == "train")
    val_count = sum(1 for s in split_map.values() if s == "val")
    test_count = sum(1 for s in split_map.values() if s == "test")

    # Within reasonable tolerance of 60%, 20%, 20%
    assert 0.50 <= train_count / n <= 0.70
    assert 0.15 <= val_count / n <= 0.25
    assert 0.15 <= test_count / n <= 0.25
