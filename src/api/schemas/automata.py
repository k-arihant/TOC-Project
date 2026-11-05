"""Automata operations request and response schemas."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class ValidateRequest(BaseModel):
    workflow_id: int
    case_id: str = "adhoc-1"
    activities: list[str]


class ValidateResponse(BaseModel):
    case_id: str
    verdict: str = Field(..., description="'VALID_COMPLETE' | 'VALID_PREFIX' | 'INVALID'")
    reason_code: Optional[str] = None
    fail_index: Optional[int] = None
    fail_state: Optional[str] = None
    fail_event: Optional[str] = None
    allowed_events: list[str] = []
    state_path: list[str] = []
    explanation: list[str] = []


class NfaToDfaRequest(BaseModel):
    use_default_retry: bool = True
    regex: Optional[str] = None


class NfaToDfaResponse(BaseModel):
    step_table: list[dict[str, Any]]
    states: list[str]
    accepting_states: list[str]
    start_state: str
    transitions: list[dict[str, Any]]


class MinimizeRequest(BaseModel):
    automaton_id: Optional[int] = None
    workflow_id: Optional[int] = None


class MinimizeResponse(BaseModel):
    min_automaton_id: Optional[int] = None
    states: list[str]
    accepting_states: list[str]
    start_state: str
    merged_partition: dict[str, list[str]]
    transitions: list[dict[str, Any]]


class ReachabilityResponse(BaseModel):
    automaton_id: int
    reachable_states: list[str]
    unreachable_states: list[str]
    dead_states: list[str]
    useful_states: list[str]


class EquivalenceRequest(BaseModel):
    automaton_id_1: int
    automaton_id_2: int


class EquivalenceResponse(BaseModel):
    equivalent: bool
    counterexample: Optional[list[str]] = None
