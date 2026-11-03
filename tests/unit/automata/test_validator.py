"""Tests reproducing the exact trace validation table from Doc 04 §2."""

from pathlib import Path

import pytest
import yaml

from src.automata.loader import load_workflow
from src.automata.validator import validate_trace
from src.common.types import FsmVerdict

SPEC_PATH = Path("workflows/order_payment/workflow.yaml")
MAP_PATH = Path("workflows/order_payment/activity_map.yaml")


@pytest.fixture
def workflow_dfa():
    return load_workflow(SPEC_PATH)


@pytest.fixture
def activity_map():
    with open(MAP_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f).get("mappings", {})


def test_trace_table_row_1_happy_path(workflow_dfa, activity_map):
    # OC PI PA PK SH DL CL -> VALID_COMPLETE
    trace = ["OC", "PI", "PA", "PK", "SH", "DL", "CL"]
    result = validate_trace(workflow_dfa, "c1", trace, activity_map)
    assert result.verdict == FsmVerdict.VALID_COMPLETE
    assert result.state_path == ["S0", "S1", "S2", "S4", "S5", "S6", "S7", "S12"]
    assert result.fail_index is None


def test_trace_table_row_2_one_retry(workflow_dfa, activity_map):
    # OC PI PF PI PA PK SH DL CL -> VALID_COMPLETE (valid process variation)
    trace = ["OC", "PI", "PF", "PI", "PA", "PK", "SH", "DL", "CL"]
    result = validate_trace(workflow_dfa, "c2", trace, activity_map)
    assert result.verdict == FsmVerdict.VALID_COMPLETE
    assert result.state_path == ["S0", "S1", "S2", "S3", "S2", "S4", "S5", "S6", "S7", "S12"]


def test_trace_table_row_3_cancel_before_payment(workflow_dfa, activity_map):
    # OC CX CL -> VALID_COMPLETE
    trace = ["OC", "CX", "CL"]
    result = validate_trace(workflow_dfa, "c3", trace, activity_map)
    assert result.verdict == FsmVerdict.VALID_COMPLETE
    assert result.state_path == ["S0", "S1", "S8", "S12"]


def test_trace_table_row_4_return_with_refund(workflow_dfa, activity_map):
    # OC PI PA PK SH DL RR RC CL -> VALID_COMPLETE
    trace = ["OC", "PI", "PA", "PK", "SH", "DL", "RR", "RC", "CL"]
    result = validate_trace(workflow_dfa, "c4", trace, activity_map)
    assert result.verdict == FsmVerdict.VALID_COMPLETE
    assert result.state_path == ["S0", "S1", "S2", "S4", "S5", "S6", "S7", "S10", "S11", "S12"]


def test_trace_table_row_5_prefix_in_progress(workflow_dfa, activity_map):
    # OC PI PA PK SH -> VALID_PREFIX (legal so far, not closed)
    trace = ["OC", "PI", "PA", "PK", "SH"]
    result = validate_trace(workflow_dfa, "c5", trace, activity_map)
    assert result.verdict == FsmVerdict.VALID_PREFIX
    assert result.state_path == ["S0", "S1", "S2", "S4", "S5", "S6"]
    assert result.fail_index is None


def test_trace_table_row_6_illegal_transition_skip_packing(workflow_dfa, activity_map):
    # OC PI PA SH -> INVALID (ILLEGAL_TRANSITION at index 3 in S4 Paid: skipped packing)
    trace = ["OC", "PI", "PA", "SH"]
    result = validate_trace(workflow_dfa, "c6", trace, activity_map)
    assert result.verdict == FsmVerdict.INVALID
    assert result.reason_code == "ILLEGAL_TRANSITION"
    assert result.fail_index == 3
    assert result.fail_state == "S4"
    assert result.fail_event == "SH"
    assert set(result.allowed_events) == {"OrderPacked", "OrderCancelled"}


def test_trace_table_row_7_illegal_transition_shipped_without_payment(workflow_dfa, activity_map):
    # OC PK -> INVALID (ILLEGAL_TRANSITION at index 1 in S1 Created)
    trace = ["OC", "PK"]
    result = validate_trace(workflow_dfa, "c7", trace, activity_map)
    assert result.verdict == FsmVerdict.INVALID
    assert result.reason_code == "ILLEGAL_TRANSITION"
    assert result.fail_index == 1
    assert result.fail_state == "S1"
    assert result.fail_event == "PK"
    assert set(result.allowed_events) == {"PaymentInitiated", "OrderCancelled"}


def test_trace_table_row_8_event_after_closed(workflow_dfa, activity_map):
    # OC PI PA PK SH DL CL PK -> INVALID (EVENT_AFTER_FINAL at index 7)
    trace = ["OC", "PI", "PA", "PK", "SH", "DL", "CL", "PK"]
    result = validate_trace(workflow_dfa, "c8", trace, activity_map)
    assert result.verdict == FsmVerdict.INVALID
    assert result.reason_code == "EVENT_AFTER_FINAL"
    assert result.fail_index == 7
    assert result.fail_state == "S12"


def test_trace_table_row_9_excessive_retries_valid_under_dfa(workflow_dfa, activity_map):
    # 6 retries: OC PI PF PI PF PI PF PI PF PI PF PI PF PI PA PK SH DL CL -> VALID_COMPLETE
    # (Formal motivation for ML: the DFA considers 6 retries legal!)
    trace = ["OC"] + ["PI", "PF"] * 6 + ["PI", "PA", "PK", "SH", "DL", "CL"]
    result = validate_trace(workflow_dfa, "c9", trace, activity_map)
    assert result.verdict == FsmVerdict.VALID_COMPLETE
    assert result.fail_index is None


def test_trace_table_row_10_unknown_event(workflow_dfa, activity_map):
    # OC FOO -> INVALID (UNKNOWN_EVENT at index 1)
    trace = ["OC", "FOO"]
    result = validate_trace(workflow_dfa, "c10", trace, activity_map)
    assert result.verdict == FsmVerdict.INVALID
    assert result.reason_code == "UNKNOWN_EVENT"
    assert result.fail_index == 1
    assert result.fail_event == "FOO"
