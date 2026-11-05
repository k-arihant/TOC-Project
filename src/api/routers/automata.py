"""Automata operations router."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.schemas.automata import (
    EquivalenceRequest,
    EquivalenceResponse,
    MinimizeRequest,
    MinimizeResponse,
    NfaToDfaRequest,
    NfaToDfaResponse,
    ReachabilityResponse,
    ValidateRequest,
    ValidateResponse,
)
from src.automata.conversion import nfa_to_dfa_with_subsets
from src.automata.dfa import DFA
from src.automata.equivalence import equivalent
from src.automata.explain import explain_fsm
from src.automata.loader import load_workflow
from src.automata.minimization import minimise
from src.automata.nfa import build_payment_block_nfa
from src.automata.reachability import analyse
from src.automata.validator import validate_trace
from src.db.models import Automaton
from src.db.repositories.workflow_repo import WorkflowRepository
from src.db.session import get_db

router = APIRouter(prefix="/automata", tags=["Automata"])


def _dfa_from_model(auto: Automaton) -> DFA:
    """Reconstruct an in-memory DFA object from an Automaton ORM model."""
    states = {s.state_name for s in auto.states}
    start_state = next((s.state_name for s in auto.states if s.is_initial), "S0")
    accepting = {s.state_name for s in auto.states if s.is_accepting}
    dead_state = next((s.state_name for s in auto.states if s.is_dead), "S_dead")
    alphabet = {t.event.name for t in auto.transitions if t.event}
    delta = {}
    for t in auto.transitions:
        if t.event:
            delta[(t.from_state, t.event.name)] = t.to_state

    return DFA(
        states=states,
        alphabet=alphabet,
        delta=delta,
        start_state=start_state,
        accepting_states=accepting,
        dead_state=dead_state,
        state_names={s.state_name: s.state_name for s in auto.states},
    )


@router.post("/validate", response_model=ValidateResponse)
def validate_activities(
    payload: ValidateRequest,
    db: Session = Depends(get_db),
) -> ValidateResponse:
    """Validate an ad-hoc sequence of activities against a workflow DFA."""
    repo = WorkflowRepository(db)
    auto = repo.get_automaton_by_kind(payload.workflow_id, "DFA")
    if auto:
        dfa = _dfa_from_model(auto)
    else:
        # Fallback to default specification
        dfa = load_workflow("workflows/order_payment/workflow.yaml")

    result = validate_trace(
        dfa=dfa,
        case_id=payload.case_id,
        activities=payload.activities,
    )
    explanation = explain_fsm(result)

    return ValidateResponse(
        case_id=result.case_id,
        verdict=result.verdict.value,
        reason_code=result.reason_code,
        fail_index=result.fail_index,
        fail_state=result.fail_state,
        fail_event=result.fail_event,
        allowed_events=result.allowed_events or [],
        state_path=result.state_path,
        explanation=explanation,
    )


@router.post("/nfa-to-dfa", response_model=NfaToDfaResponse)
def convert_nfa_to_dfa(payload: NfaToDfaRequest) -> NfaToDfaResponse:
    """Run subset construction on the payment retry NFA and return step table."""
    nfa = build_payment_block_nfa()
    dfa, subset_map = nfa_to_dfa_with_subsets(nfa)

    step_table: list[dict[str, Any]] = []
    for dfa_state, subset in subset_map.items():
        step_table.append(
            {
                "dfa_state": dfa_state,
                "nfa_subset": sorted(subset),
                "is_accepting": dfa_state in dfa.accepting_states,
            }
        )

    transitions: list[dict[str, Any]] = []
    for (q, sym), target in dfa.delta.items():
        transitions.append({"from": q, "symbol": sym, "to": target})

    return NfaToDfaResponse(
        step_table=step_table,
        states=sorted(dfa.states),
        accepting_states=sorted(dfa.accepting_states),
        start_state=dfa.start_state,
        transitions=transitions,
    )


@router.post("/minimize", response_model=MinimizeResponse)
def minimize_dfa(
    payload: MinimizeRequest,
    db: Session = Depends(get_db),
) -> MinimizeResponse:
    """Minimise a DFA using Moore's partition refinement algorithm."""
    repo = WorkflowRepository(db)
    dfa: DFA
    if payload.automaton_id:
        auto = repo.get_automaton(payload.automaton_id)
        if not auto:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "AUTOMATON_NOT_FOUND", "message": f"Automaton {payload.automaton_id} not found"},
            )
        dfa = _dfa_from_model(auto)
    elif payload.workflow_id:
        auto = repo.get_automaton_by_kind(payload.workflow_id, "DFA")
        if not auto:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "AUTOMATON_NOT_FOUND", "message": f"DFA for workflow {payload.workflow_id} not found"},
            )
        dfa = _dfa_from_model(auto)
    else:
        dfa = load_workflow("workflows/order_payment/workflow.yaml")

    min_dfa, partition = minimise(dfa)

    transitions: list[dict[str, Any]] = []
    for (q, sym), target in min_dfa.delta.items():
        transitions.append({"from": q, "symbol": sym, "to": target})

    return MinimizeResponse(
        min_automaton_id=None,
        states=sorted(min_dfa.states),
        accepting_states=sorted(min_dfa.accepting_states),
        start_state=min_dfa.start_state,
        merged_partition=partition,
        transitions=transitions,
    )


@router.get("/{id}/reachability", response_model=ReachabilityResponse)
def get_automaton_reachability(
    id: int,
    db: Session = Depends(get_db),
) -> ReachabilityResponse:
    """Compute reachable, unreachable, dead, and useful states for an automaton."""
    repo = WorkflowRepository(db)
    auto = repo.get_automaton(id)
    if not auto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "AUTOMATON_NOT_FOUND", "message": f"Automaton {id} not found"},
        )

    dfa = _dfa_from_model(auto)
    report = analyse(dfa)

    return ReachabilityResponse(
        automaton_id=id,
        reachable_states=sorted(report.reachable),
        unreachable_states=sorted(report.unreachable),
        dead_states=sorted(report.dead),
        useful_states=sorted(report.useful),
    )


@router.post("/equivalence", response_model=EquivalenceResponse)
def check_automata_equivalence(
    payload: EquivalenceRequest,
    db: Session = Depends(get_db),
) -> EquivalenceResponse:
    """Test language equivalence between two DFAs and return counter-example if different."""
    repo = WorkflowRepository(db)
    a1 = repo.get_automaton(payload.automaton_id_1)
    a2 = repo.get_automaton(payload.automaton_id_2)

    if not a1:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "AUTOMATON_NOT_FOUND", "message": f"Automaton {payload.automaton_id_1} not found"},
        )
    if not a2:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "AUTOMATON_NOT_FOUND", "message": f"Automaton {payload.automaton_id_2} not found"},
        )

    d1 = _dfa_from_model(a1)
    d2 = _dfa_from_model(a2)

    is_equiv, counter_ex = equivalent(d1, d2)
    return EquivalenceResponse(
        equivalent=is_equiv,
        counterexample=counter_ex,
    )
