"""Tests for anomaly injection and automated DFA label verification (Doc 06 §9)."""

from src.automata.loader import load_workflow
from src.automata.validator import validate_trace
from src.common.types import FsmVerdict
from src.workflow_ml.injector import AnomalyInjector
from src.workflow_ml.simulator import WorkflowSimulator


def test_label_verification_rule_violations_and_statistical_anomalies():
    """Mandatory label-verification test:
    - Every rule_violation must be INVALID under DFA.
    - Every statistical_anomaly must be VALID_COMPLETE under DFA.
    - Every normal/valid_variation must be VALID_COMPLETE.
    """
    dfa = load_workflow("workflows/order_payment/workflow.yaml")
    sim = WorkflowSimulator(seed=99)
    raw_cases = sim.generate_dataset(n_cases=200)

    injector = AnomalyInjector(dfa=dfa, seed=99)
    cases = injector.inject_anomalies(raw_cases)

    rule_violation_count = 0
    statistical_anomaly_count = 0

    for c in cases:
        result = validate_trace(dfa, c.trace.case_id, c.trace.activities)

        if c.label_class == "rule_violation":
            rule_violation_count += 1
            assert result.verdict == FsmVerdict.INVALID, (
                f"Rule violation '{c.anomaly_type}' in case '{c.trace.case_id}' was NOT invalid! "
                f"Activities: {c.trace.activities}"
            )
        elif c.label_class == "statistical_anomaly":
            statistical_anomaly_count += 1
            assert result.verdict == FsmVerdict.VALID_COMPLETE, (
                f"Statistical anomaly '{c.anomaly_type}' in case '{c.trace.case_id}' was NOT valid_complete! "
                f"Activities: {c.trace.activities}"
            )
        else:
            assert result.verdict == FsmVerdict.VALID_COMPLETE

    assert rule_violation_count > 0, "No rule violations were injected!"
    assert statistical_anomaly_count > 0, "No statistical anomalies were injected!"


def test_injector_seed_determinism():
    """Same seed yields identical injected anomalies."""
    sim1 = WorkflowSimulator(seed=101)
    raw1 = sim1.generate_dataset(n_cases=60)
    inj1 = AnomalyInjector(seed=101)
    cases1 = inj1.inject_anomalies(raw1)

    sim2 = WorkflowSimulator(seed=101)
    raw2 = sim2.generate_dataset(n_cases=60)
    inj2 = AnomalyInjector(seed=101)
    cases2 = inj2.inject_anomalies(raw2)

    for c1, c2 in zip(cases1, cases2):
        assert c1.label_class == c2.label_class
        assert c1.anomaly_type == c2.anomaly_type
        assert c1.trace.activities == c2.trace.activities
