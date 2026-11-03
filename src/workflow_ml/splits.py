"""Case-level stratified splitting with held-out anomaly types."""

from typing import Any, Dict, List, Optional

import numpy as np

from src.workflow_ml.simulator import SimulatedCase


def split_cases(
    cases: List[SimulatedCase],
    config: Optional[Dict[str, Any]] = None,
    seed: int = 0,
) -> Dict[str, str]:
    """Perform case-level stratified split into train, validation, and test sets.

    Follows Doc 06 §6:
      - Unit of splitting: case_id.
      - Default proportions: train 60% / validation 20% / test 20%.
      - Held-out anomaly types (≥1 rule type and ≥1 statistical type) are routed strictly to 'test'.
      - Remaining cases are stratified by label_class across train/val/test.
      - Invariant: Zero leakage (no case_id appears in multiple splits).

    Returns:
        Dictionary mapping case_id -> split ('train', 'val', 'test').
    """
    splits_cfg = (config or {}).get("splits", {})
    train_ratio = float(splits_cfg.get("train", 0.60))
    val_ratio = float(splits_cfg.get("val", 0.20))
    test_ratio = float(splits_cfg.get("test", 0.20))

    total_r = train_ratio + val_ratio + test_ratio
    train_ratio /= total_r
    val_ratio /= total_r
    test_ratio /= total_r

    held_out_rule = set(splits_cfg.get("held_out_rule_types", ["event_after_closed"]))
    held_out_stat = set(splits_cfg.get("held_out_statistical_types", ["burst_fast"]))
    held_out_types = held_out_rule | held_out_stat

    rng = np.random.default_rng(seed)

    split_map: Dict[str, str] = {}

    # 1. Assign held-out anomaly cases strictly to 'test'
    held_out_cases = [c for c in cases if c.anomaly_type in held_out_types]
    for c in held_out_cases:
        split_map[c.trace.case_id] = "test"

    # 2. Group remaining cases by label_class for stratified splitting
    remaining_cases = [c for c in cases if c.anomaly_type not in held_out_types]
    by_class: Dict[str, List[SimulatedCase]] = {}
    for c in remaining_cases:
        by_class.setdefault(c.label_class, []).append(c)

    # 3. Stratify each class
    for label_class, class_cases in by_class.items():
        case_ids = [c.trace.case_id for c in class_cases]
        rng.shuffle(case_ids)

        n = len(case_ids)
        n_train = int(np.round(n * train_ratio))
        n_val = int(np.round(n * val_ratio))

        train_ids = case_ids[:n_train]
        val_ids = case_ids[n_train : n_train + n_val]
        test_ids = case_ids[n_train + n_val :]

        for cid in train_ids:
            split_map[cid] = "train"
        for cid in val_ids:
            split_map[cid] = "val"
        for cid in test_ids:
            split_map[cid] = "test"

    return split_map
