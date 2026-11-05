"""Shared test client fixtures for API unit tests."""

import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
import yaml
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.main import create_app
from src.automata.loader import load_workflow
from src.automata.minimization import minimise
from src.automata.nfa import build_payment_block_nfa
from src.db.base import Base
from src.db.repositories.workflow_repo import WorkflowRepository
from src.db.session import get_db

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session")
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    repo = WorkflowRepository(session)

    with open("workflows/order_payment/workflow.yaml", encoding="utf-8") as f:
        spec = yaml.safe_load(f)

    # Seed initial test workflow
    wf = repo.create_workflow(
        name=spec.get("name", "Online Order & Payment Lifecycle"),
        version=spec.get("version", "1.0.0"),
        description=spec.get("description", "").strip(),
    )
    events = [(item["code"], item["name"]) for item in spec.get("alphabet", [])]
    created_events = repo.add_events(wf.workflow_id, events)
    event_id_map = {e.name: e.event_id for e in created_events}

    # Seed base DFA
    dfa = load_workflow("workflows/order_payment/workflow.yaml")
    states_list = [
        {
            "name": s,
            "initial": (s == dfa.start_state),
            "accepting": (s in dfa.accepting_states),
            "dead": (s == dfa.dead_state),
        }
        for s in dfa.states
    ]
    trans_list = [
        {"from": q, "event_id": event_id_map.get(sym), "to": target}
        for (q, sym), target in dfa.delta.items()
    ]
    base_auto = repo.create_automaton(wf.workflow_id, "DFA", "Base Complete DFA", states_list, trans_list)

    # Seed Moore Minimised DFA
    min_dfa, partition = minimise(dfa)
    min_states_list = [
        {
            "name": s,
            "initial": (s == min_dfa.start_state),
            "accepting": (s in min_dfa.accepting_states),
            "dead": (s == min_dfa.dead_state),
            "merged_from": partition.get(s, [s]),
        }
        for s in min_dfa.states
    ]
    min_trans_list = [
        {"from": q, "event_id": event_id_map.get(sym), "to": target}
        for (q, sym), target in min_dfa.delta.items()
    ]
    repo.create_automaton(
        wf.workflow_id,
        "MIN_DFA",
        "Moore Minimised DFA",
        min_states_list,
        min_trans_list,
        derived_from=base_auto.automaton_id,
    )

    # Seed NFA
    nfa = build_payment_block_nfa()
    nfa_states_list = [
        {"name": s, "initial": (s == nfa.start_state), "accepting": (s in nfa.accepting_states), "dead": False}
        for s in nfa.states
    ]
    nfa_trans_list = []
    for (q, sym), targets in nfa.delta.items():
        for target in targets:
            nfa_trans_list.append({"from": q, "event_id": event_id_map.get(sym), "to": target})
    repo.create_automaton(
        wf.workflow_id,
        "NFA",
        "Thompson Payment Retry NFA",
        nfa_states_list,
        nfa_trans_list,
        derived_from=base_auto.automaton_id,
    )

    session.close()
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client(setup_test_db):
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
