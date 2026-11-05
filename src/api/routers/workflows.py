"""Workflows and Automata retrieval router."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.api.schemas.workflows import (
    AutomatonResponse,
    AutomatonStateSchema,
    AutomatonTransitionSchema,
    WorkflowResponse,
)
from src.db.models import Automaton
from src.db.repositories.workflow_repo import WorkflowRepository
from src.db.session import get_db

router = APIRouter(tags=["Workflows"])


def _generate_dot(auto: Automaton, show_dead: bool = False) -> str:
    """Generate Graphviz DOT string for an automaton."""
    start_state = next((s.state_name for s in auto.states if s.is_initial), "")
    lines = [
        "digraph Automaton {",
        '    rankdir="LR";',
        '    node [fontname="Helvetica", fontsize=11];',
        '    edge [fontname="Helvetica", fontsize=10];',
        '    __start [shape=none, label="", width=0, height=0];',
        f'    __start -> "{start_state}";',
    ]
    for s in auto.states:
        if s.is_dead and not show_dead:
            continue
        shape = "doublecircle" if s.is_accepting else "circle"
        lines.append(f'    "{s.state_name}" [shape={shape}];')

    for t in auto.transitions:
        sym = t.event.name if t.event else "ε"
        lines.append(f'    "{t.from_state}" -> "{t.to_state}" [label="{sym}"];')

    lines.append("}")
    return "\n".join(lines)


@router.get("/workflows", response_model=list[WorkflowResponse])
def list_workflows(db: Session = Depends(get_db)) -> list[WorkflowResponse]:
    """List all registered process workflows."""
    repo = WorkflowRepository(db)
    workflows = repo.list_workflows()
    results = []
    for wf in workflows:
        results.append(
            WorkflowResponse(
                workflow_id=wf.workflow_id,
                name=wf.name,
                version=wf.version,
                description=wf.description,
                created_at=wf.created_at,
                event_count=len(wf.events),
                automaton_count=len(wf.automata),
            )
        )
    return results


@router.get("/workflows/{id}/automaton", response_model=AutomatonResponse)
def get_workflow_automaton(
    id: int,
    kind: str = Query("DFA", pattern="^(DFA|NFA|MIN_DFA|BOUNDED_DFA)$"),
    db: Session = Depends(get_db),
) -> AutomatonResponse:
    """Retrieve automaton specification (states, transitions, DOT) for a workflow."""
    repo = WorkflowRepository(db)
    wf = repo.get_workflow(id)
    if not wf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "WORKFLOW_NOT_FOUND", "message": f"Workflow {id} not found"},
        )

    auto = repo.get_automaton_by_kind(id, kind)
    if not auto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "AUTOMATON_NOT_FOUND",
                "message": f"Automaton of kind '{kind}' for workflow {id} not found",
            },
        )

    states = [
        AutomatonStateSchema(
            name=s.state_name,
            initial=s.is_initial,
            accepting=s.is_accepting,
            dead=s.is_dead,
            merged_from=s.merged_from,
        )
        for s in auto.states
    ]
    transitions = [
        AutomatonTransitionSchema(
            from_state=t.from_state,
            to_state=t.to_state,
            event_code=t.event.code if t.event else None,
            event_name=t.event.name if t.event else None,
        )
        for t in auto.transitions
    ]
    accepting_states = [s.state_name for s in auto.states if s.is_accepting]
    start_state = next((s.state_name for s in auto.states if s.is_initial), "")
    dot = _generate_dot(auto)

    return AutomatonResponse(
        automaton_id=auto.automaton_id,
        workflow_id=auto.workflow_id,
        kind=auto.kind,
        label=auto.label,
        states=states,
        transitions=transitions,
        accepting_states=accepting_states,
        start_state=start_state,
        dot=dot,
    )
