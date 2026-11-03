"""Tests for workflow trace simulation and seed reproducibility."""

from src.automata.loader import load_workflow
from src.automata.validator import validate_trace
from src.common.types import FsmVerdict
from src.workflow_ml.simulator import WorkflowSimulator


def test_simulator_seed_reproducibility():
    """Seed reproducibility test (Doc 06 §9): Same seed yields identical traces."""
    sim1 = WorkflowSimulator(seed=42)
    cases1 = sim1.generate_dataset(n_cases=50)

    sim2 = WorkflowSimulator(seed=42)
    cases2 = sim2.generate_dataset(n_cases=50)

    assert len(cases1) == len(cases2)
    for c1, c2 in zip(cases1, cases2):
        assert c1.trace.case_id == c2.trace.case_id
        assert c1.trace.activities == c2.trace.activities
        assert c1.label_class == c2.label_class
        for e1, e2 in zip(c1.trace.events, c2.trace.events):
            assert e1.timestamp == e2.timestamp


def test_simulator_generates_strictly_valid_traces():
    """All unmutated simulated cases must be VALID_COMPLETE under the formal DFA."""
    dfa = load_workflow("workflows/order_payment/workflow.yaml")
    sim = WorkflowSimulator(seed=123)
    cases = sim.generate_dataset(n_cases=100)

    for c in cases:
        result = validate_trace(dfa, c.trace.case_id, c.trace.activities)
        assert result.verdict == FsmVerdict.VALID_COMPLETE, (
            f"Case '{c.trace.case_id}' was generated as invalid! Path: {result.state_path}"
        )
        assert c.label_class in {"normal", "valid_variation"}
        assert c.anomaly_type == "none"
