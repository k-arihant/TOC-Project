from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.common.types import (
    DetectorScore,
    Event,
    Factor,
    FinalLabel,
    FsmResult,
    FsmVerdict,
    HybridDecision,
)
from src.db.base import Base
from src.db.repositories.dataset_repo import DatasetRepository
from src.db.repositories.evaluation_repo import EvaluationRepository
from src.db.repositories.hybrid_repo import HybridRepository
from src.db.repositories.model_repo import ModelRepository
from src.db.repositories.packet_repo import PacketRepository
from src.db.repositories.workflow_repo import WorkflowRepository


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


def test_workflow_repository_crud(db_session: Session):
    repo = WorkflowRepository(db_session)
    wf = repo.create_workflow(name="Order", version="1.0.0", description="Desc")
    assert wf.workflow_id is not None

    events = repo.add_events(wf.workflow_id, [("OC", "OrderCreated"), ("PI", "PaymentInitiated")])
    assert len(events) == 2

    auto = repo.create_automaton(
        workflow_id=wf.workflow_id,
        kind="DFA",
        label="Base DFA",
        states=[{"name": "S0", "initial": True}, {"name": "S1", "accepting": True}],
        transitions=[{"from": "S0", "to": "S1", "event_id": events[0].event_id}],
    )
    assert auto.automaton_id is not None

    found_wf = repo.get_by_name_and_version("Order", "1.0.0")
    assert found_wf is not None
    assert found_wf.workflow_id == wf.workflow_id


def test_dataset_repository_crud(db_session: Session):
    wf_repo = WorkflowRepository(db_session)
    wf = wf_repo.create_workflow(name="E-Commerce", version="2.0.0")

    ds_repo = DatasetRepository(db_session)
    ds = ds_repo.create_dataset(
        workflow_id=wf.workflow_id,
        name="Log 2026",
        source_kind="synthetic",
        label_semantics="injected",
        seed=10,
    )
    assert ds.dataset_id is not None

    case = ds_repo.add_case(
        dataset_id=ds.dataset_id, case_id="CASE-1", label_class="normal", split="train"
    )
    ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    evs = [
        Event(case_id="CASE-1", activity="OrderCreated", timestamp=ts),
        Event(case_id="CASE-1", activity="OrderClosed", timestamp=ts),
    ]
    ds_repo.add_events(case.case_pk, evs)

    traces = ds_repo.get_traces_for_dataset(ds.dataset_id, split="train")
    assert len(traces) == 1
    assert traces[0].case_id == "CASE-1"
    assert len(traces[0].events) == 2


def test_model_and_hybrid_repository_crud(db_session: Session):
    wf_repo = WorkflowRepository(db_session)
    wf = wf_repo.create_workflow(name="WF", version="1.0.0")
    auto = wf_repo.create_automaton(wf.workflow_id, "DFA", "DFA", [{"name": "S0"}], [])

    ds_repo = DatasetRepository(db_session)
    ds = ds_repo.create_dataset(wf.workflow_id, "DS", "synthetic", "injected")
    case = ds_repo.add_case(ds.dataset_id, "C-1", "normal")

    # Model Run & Prediction
    m_repo = ModelRepository(db_session)
    m_run = m_repo.create_model_run(
        ds.dataset_id, "isolation_forest", {"n_est": 100}, seed=42, threshold=0.95
    )

    score = DetectorScore(
        case_id="C-1",
        detector="isolation_forest",
        raw_score=0.2,
        norm_score=0.4,
        threshold=0.95,
        is_anomaly=False,
        factors=[Factor(name="feat", value=1.0, reference=1.0, note="ok")],
    )
    pred = m_repo.record_prediction(case.case_pk, m_run.model_run_id, score)
    assert pred.prediction_id is not None

    # Hybrid Decision
    h_repo = HybridRepository(db_session)
    fsm_res = FsmResult(case_id="C-1", verdict=FsmVerdict.VALID_COMPLETE, state_path=["S0"])
    fsm_obj = h_repo.record_fsm_result(case.case_pk, auto.automaton_id, fsm_res)

    decision = HybridDecision(
        case_id="C-1",
        final_label=FinalLabel.NORMAL,
        fsm=fsm_res,
        ml=[score],
        explanation=["Normal execution."],
    )
    dec_obj = h_repo.record_decision(
        case_pk=case.case_pk,
        fsm_result_id=fsm_obj.fsm_result_id,
        decision=decision,
        prediction_ids=[pred.prediction_id],
    )
    assert dec_obj.decision_id is not None
    assert dec_obj.final_label == "NORMAL"


def test_evaluation_repository_crud(db_session: Session):
    wf_repo = WorkflowRepository(db_session)
    wf = wf_repo.create_workflow(name="Eval WF", version="1.0.0")
    ds_repo = DatasetRepository(db_session)
    ds = ds_repo.create_dataset(wf.workflow_id, "Eval DS", "synthetic", "injected")

    eval_repo = EvaluationRepository(db_session)
    run = eval_repo.create_evaluation_run(
        dataset_id=ds.dataset_id,
        detector="hybrid",
        split="test",
        n_cases=100,
        tp=20,
        fp=2,
        tn=75,
        fn=3,
        type_metrics={"skip_event": {"n_cases": 10, "n_detected": 9}},
    )
    assert run.eval_id is not None
    assert len(run.type_metrics) == 1
    assert run.type_metrics[0].anomaly_type == "skip_event"


def test_packet_repository_crud(db_session: Session):
    p_repo = PacketRepository(db_session)
    exp = p_repo.create_experiment(
        name="TCP Lab",
        source_description="Loopback traffic",
        profile="strict",
    )
    assert exp.experiment_id is not None

    flows_data = [
        {
            "src_ip": "127.0.0.1",
            "src_port": 1234,
            "dst_ip": "127.0.0.1",
            "dst_port": 80,
            "n_events": 3,
            "verdict": "ACCEPTED_CLEAN",
            "events": ["SYN", "SYNACK", "ACK"],
        }
    ]
    flow_models = p_repo.record_flows(exp.experiment_id, flows_data)
    assert len(flow_models) == 1
    assert flow_models[0].verdict == "ACCEPTED_CLEAN"
