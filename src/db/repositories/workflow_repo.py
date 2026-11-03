from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import Automaton, AutomatonState, AutomatonTransition, Workflow, WorkflowEvent


class WorkflowRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_workflow(
        self,
        name: str,
        version: str,
        description: str | None = None,
    ) -> Workflow:
        wf = Workflow(name=name, version=version, description=description)
        self.db.add(wf)
        self.db.commit()
        self.db.refresh(wf)
        return wf

    def get_workflow(self, workflow_id: int) -> Workflow | None:
        stmt = select(Workflow).where(Workflow.workflow_id == workflow_id)
        return self.db.scalars(stmt).first()

    def get_by_name_and_version(self, name: str, version: str) -> Workflow | None:
        stmt = select(Workflow).where(Workflow.name == name, Workflow.version == version)
        return self.db.scalars(stmt).first()

    def list_workflows(self) -> list[Workflow]:
        stmt = select(Workflow).order_by(Workflow.workflow_id)
        return list(self.db.scalars(stmt).all())

    def add_events(self, workflow_id: int, events: list[tuple[str, str]]) -> list[WorkflowEvent]:
        created_events: list[WorkflowEvent] = []
        for code, name in events:
            evt = WorkflowEvent(workflow_id=workflow_id, code=code, name=name)
            self.db.add(evt)
            created_events.append(evt)
        self.db.commit()
        return created_events

    def get_event_by_name(self, workflow_id: int, name: str) -> WorkflowEvent | None:
        stmt = select(WorkflowEvent).where(
            WorkflowEvent.workflow_id == workflow_id,
            WorkflowEvent.name == name,
        )
        return self.db.scalars(stmt).first()

    def create_automaton(
        self,
        workflow_id: int,
        kind: str,
        label: str,
        states: list[dict],
        transitions: list[dict],
        derived_from: int | None = None,
    ) -> Automaton:
        auto = Automaton(
            workflow_id=workflow_id,
            kind=kind,
            label=label,
            derived_from=derived_from,
        )
        self.db.add(auto)
        self.db.flush()

        for s in states:
            state_obj = AutomatonState(
                automaton_id=auto.automaton_id,
                state_name=s["name"],
                is_initial=s.get("initial", False),
                is_accepting=s.get("accepting", False),
                is_dead=s.get("dead", False),
                merged_from=s.get("merged_from"),
            )
            self.db.add(state_obj)
        self.db.flush()

        for t in transitions:
            trans_obj = AutomatonTransition(
                automaton_id=auto.automaton_id,
                from_state=t["from"],
                event_id=t.get("event_id"),
                to_state=t["to"],
            )
            self.db.add(trans_obj)

        self.db.commit()
        self.db.refresh(auto)
        return auto

    def get_automaton(self, automaton_id: int) -> Automaton | None:
        stmt = select(Automaton).where(Automaton.automaton_id == automaton_id)
        return self.db.scalars(stmt).first()

    def get_automaton_by_kind(self, workflow_id: int, kind: str) -> Automaton | None:
        stmt = select(Automaton).where(
            Automaton.workflow_id == workflow_id,
            Automaton.kind == kind,
        )
        return self.db.scalars(stmt).first()
