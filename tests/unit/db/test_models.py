from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from src.db.base import Base
from src.db.models import (
    Automaton,
    AutomatonState,
    Case,
    Dataset,
    EventLog,
    ExplanationModel,
    FsmResultModel,
    HybridDecisionModel,
    PacketExperimentModel,
    PacketFlowModel,
    Workflow,
    WorkflowEvent,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_workflow_and_automata_models(db_session: Session):
    # Workflow
    wf = Workflow(name="Order Workflow", version="1.0.0", description="Test description")
    db_session.add(wf)
    db_session.commit()
    assert wf.workflow_id is not None

    # Event
    evt = WorkflowEvent(workflow_id=wf.workflow_id, code="OC", name="OrderCreated")
    db_session.add(evt)
    db_session.commit()
    assert evt.event_id is not None

    # Automaton
    auto = Automaton(workflow_id=wf.workflow_id, kind="DFA", label="Test DFA")
    db_session.add(auto)
    db_session.commit()
    assert auto.automaton_id is not None

    # State
    state = AutomatonState(automaton_id=auto.automaton_id, state_name="S0", is_initial=True)
    db_session.add(state)
    db_session.commit()

    retrieved_wf = db_session.scalars(
        select(Workflow).where(Workflow.name == "Order Workflow")
    ).first()
    assert retrieved_wf is not None
    assert len(retrieved_wf.events) == 1
    assert len(retrieved_wf.automata) == 1


def test_dataset_and_case_models(db_session: Session):
    wf = Workflow(name="Dataset Workflow", version="1.0.0")
    db_session.add(wf)
    db_session.flush()

    ds = Dataset(
        workflow_id=wf.workflow_id,
        name="Sample Dataset",
        source_kind="synthetic",
        label_semantics="injected",
        seed=42,
    )
    db_session.add(ds)
    db_session.flush()

    c = Case(
        dataset_id=ds.dataset_id,
        case_id="CASE-001",
        label_class="normal",
        split="train",
    )
    db_session.add(c)
    db_session.flush()

    ev = EventLog(
        case_pk=c.case_pk,
        seq_index=0,
        activity="OrderCreated",
        ts=datetime.now(timezone.utc),
        attributes={"amount": 100},
    )
    db_session.add(ev)
    db_session.commit()

    retrieved_case = db_session.scalars(select(Case).where(Case.case_id == "CASE-001")).first()
    assert retrieved_case is not None
    assert len(retrieved_case.events) == 1
    assert retrieved_case.events[0].attributes["amount"] == 100


def test_hybrid_and_explanation_models(db_session: Session):
    wf = Workflow(name="Hybrid Workflow", version="1.0.0")
    db_session.add(wf)
    db_session.flush()

    auto = Automaton(workflow_id=wf.workflow_id, kind="DFA", label="Main DFA")
    db_session.add(auto)
    db_session.flush()

    ds = Dataset(
        workflow_id=wf.workflow_id,
        name="Test DS",
        source_kind="synthetic",
        label_semantics="injected",
    )
    db_session.add(ds)
    db_session.flush()

    c = Case(dataset_id=ds.dataset_id, case_id="C-99", label_class="rule_violation")
    db_session.add(c)
    db_session.flush()

    fsm = FsmResultModel(
        case_pk=c.case_pk,
        automaton_id=auto.automaton_id,
        verdict="INVALID",
        reason_code="ILLEGAL_TRANSITION",
        fail_index=1,
        fail_state="S1",
        fail_event="OrderShipped",
        allowed_events=["PaymentInitiated"],
        state_path=["S0", "S1"],
    )
    db_session.add(fsm)
    db_session.flush()

    decision = HybridDecisionModel(
        case_pk=c.case_pk,
        fsm_result_id=fsm.fsm_result_id,
        ml_policy="any",
        final_label="RULE_VIOLATION",
        reason_code="FSM_ILLEGAL_TRANSITION",
    )
    db_session.add(decision)
    db_session.flush()

    exp = ExplanationModel(
        decision_id=decision.decision_id,
        source="FSM",
        rank=0,
        text="Event 'OrderShipped' is illegal in state S1.",
    )
    db_session.add(exp)
    db_session.commit()

    retrieved = db_session.scalars(
        select(HybridDecisionModel).where(HybridDecisionModel.decision_id == decision.decision_id)
    ).first()
    assert retrieved is not None
    assert retrieved.final_label == "RULE_VIOLATION"
    assert len(retrieved.explanations) == 1
    assert "illegal" in retrieved.explanations[0].text


def test_packet_experiment_models(db_session: Session):
    exp = PacketExperimentModel(
        name="Loopback Test",
        source_description="Local test capture",
        profile="strict",
    )
    db_session.add(exp)
    db_session.flush()

    flow = PacketFlowModel(
        experiment_id=exp.experiment_id,
        src_ip="127.0.0.1",
        src_port=50000,
        dst_ip="127.0.0.1",
        dst_port=80,
        n_events=3,
        verdict="ACCEPTED_CLEAN",
    )
    db_session.add(flow)
    db_session.commit()

    retrieved = db_session.scalars(
        select(PacketExperimentModel).where(
            PacketExperimentModel.experiment_id == exp.experiment_id
        )
    ).first()
    assert retrieved is not None
    assert len(retrieved.flows) == 1
    assert retrieved.flows[0].verdict == "ACCEPTED_CLEAN"
