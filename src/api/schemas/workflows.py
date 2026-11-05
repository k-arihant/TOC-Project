"""Workflow and Automaton response schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class WorkflowResponse(BaseModel):
    workflow_id: int
    name: str
    version: str
    description: Optional[str] = None
    created_at: datetime
    event_count: int = 0
    automaton_count: int = 0


class AutomatonStateSchema(BaseModel):
    name: str
    initial: bool = False
    accepting: bool = False
    dead: bool = False
    merged_from: Optional[list[str]] = None


class AutomatonTransitionSchema(BaseModel):
    from_state: str
    to_state: str
    event_code: Optional[str] = None
    event_name: Optional[str] = None


class AutomatonResponse(BaseModel):
    automaton_id: int
    workflow_id: int
    kind: str = Field(..., description="'DFA' | 'NFA' | 'MIN_DFA'")
    label: str
    states: list[AutomatonStateSchema]
    transitions: list[AutomatonTransitionSchema]
    accepting_states: list[str]
    start_state: str
    dot: str = Field(..., description="Graphviz DOT representation")
