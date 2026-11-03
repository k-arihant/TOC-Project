from datetime import datetime, timezone

from src.common.types import Event, Trace
from src.workflow_ml.features import extract, get_feature_names

FORBIDDEN_LEAKAGE_TOKENS = [
    "fsm",
    "verdict",
    "fail_index",
    "fail_state",
    "fail_event",
    "invalid",
    "class_label",
    "anomaly_type",
    "injector",
    "case_id",
    "split",
    "ground_truth",
]


def test_feature_names_contain_no_leakage_tokens():
    """
    Mandatory leakage test per Doc 05 §2:
    Asserts feature-name list contains none of the forbidden leakage tokens.
    """
    feature_names = get_feature_names()
    assert len(feature_names) == 145

    for name in feature_names:
        lower_name = name.lower()
        for token in FORBIDDEN_LEAKAGE_TOKENS:
            assert token not in lower_name, (
                f"Feature '{name}' contains forbidden leakage token '{token}'"
            )


def test_extractor_ignores_trace_attributes():
    """
    Asserts feature extractor produces identical results regardless of extra
    attributes attached to events (e.g. injected metadata or labels).
    """
    ts1 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    ts2 = datetime(2026, 1, 1, 10, 1, 0, tzinfo=timezone.utc)

    # Clean trace
    clean_trace = Trace(
        case_id="case_clean",
        events=[
            Event(case_id="case_clean", activity="OrderCreated", timestamp=ts1),
            Event(case_id="case_clean", activity="OrderClosed", timestamp=ts2),
        ],
    )

    # Trace with adversarial/injected attribute payload
    dirty_trace = Trace(
        case_id="case_dirty_with_label",
        events=[
            Event(
                case_id="case_dirty_with_label",
                activity="OrderCreated",
                timestamp=ts1,
                attributes={"label": "rule_violation", "fsm_verdict": "INVALID"},
            ),
            Event(
                case_id="case_dirty_with_label",
                activity="OrderClosed",
                timestamp=ts2,
                attributes={"injector_param": 999, "is_anomaly": True},
            ),
        ],
    )

    matrix_clean, names_clean = extract([clean_trace])
    matrix_dirty, names_dirty = extract([dirty_trace])

    assert names_clean == names_dirty
    assert (matrix_clean == matrix_dirty).all(), (
        "Feature extraction was influenced by non-sequence attributes!"
    )
