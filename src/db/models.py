from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, StringList, utc_now

# ==============================================================================
# Domain 1: Workflows & Automata (Doc 08 §3 Member 1)
# ==============================================================================


class Workflow(Base):
    __tablename__ = "workflows"

    workflow_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    __table_args__ = (UniqueConstraint("name", "version", name="uq_workflow_name_version"),)

    events: Mapped[list["WorkflowEvent"]] = relationship(
        "WorkflowEvent", back_populates="workflow", cascade="all, delete-orphan"
    )
    automata: Mapped[list["Automaton"]] = relationship(
        "Automaton", back_populates="workflow", cascade="all, delete-orphan"
    )
    datasets: Mapped[list["Dataset"]] = relationship("Dataset", back_populates="workflow")


class WorkflowEvent(Base):
    __tablename__ = "workflow_events"

    event_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("workflows.workflow_id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        UniqueConstraint("workflow_id", "code", name="uq_wf_code"),
        UniqueConstraint("workflow_id", "name", name="uq_wf_name"),
    )

    workflow: Mapped["Workflow"] = relationship("Workflow", back_populates="events")


class Automaton(Base):
    __tablename__ = "automata"

    automaton_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("workflows.workflow_id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)  # 'DFA','NFA','MIN_DFA','BOUNDED_DFA'
    label: Mapped[str] = mapped_column(Text, nullable=False)
    derived_from: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("automata.automaton_id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    __table_args__ = (
        CheckConstraint("kind IN ('DFA','NFA','MIN_DFA','BOUNDED_DFA')", name="chk_automaton_kind"),
    )

    workflow: Mapped["Workflow"] = relationship("Workflow", back_populates="automata")
    states: Mapped[list["AutomatonState"]] = relationship(
        "AutomatonState", back_populates="automaton", cascade="all, delete-orphan"
    )
    transitions: Mapped[list["AutomatonTransition"]] = relationship(
        "AutomatonTransition",
        primaryjoin="Automaton.automaton_id == AutomatonTransition.automaton_id",
        foreign_keys="[AutomatonTransition.automaton_id]",
        back_populates="automaton",
        cascade="all, delete-orphan",
    )


class AutomatonState(Base):
    __tablename__ = "automaton_states"

    automaton_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("automata.automaton_id", ondelete="CASCADE"), primary_key=True
    )
    state_name: Mapped[str] = mapped_column(Text, primary_key=True)
    is_initial: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_accepting: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_dead: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    merged_from: Mapped[list[str]] = mapped_column(StringList, nullable=True)

    automaton: Mapped["Automaton"] = relationship("Automaton", back_populates="states")


class AutomatonTransition(Base):
    __tablename__ = "automaton_transitions"

    transition_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    automaton_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("automata.automaton_id", ondelete="CASCADE"), nullable=False
    )
    from_state: Mapped[str] = mapped_column(Text, nullable=False)
    event_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("workflow_events.event_id"), nullable=True
    )
    to_state: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["automaton_id", "from_state"],
            ["automaton_states.automaton_id", "automaton_states.state_name"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["automaton_id", "to_state"],
            ["automaton_states.automaton_id", "automaton_states.state_name"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("automaton_id", "from_state", "event_id", name="uq_automaton_transition"),
    )

    automaton: Mapped["Automaton"] = relationship(
        "Automaton",
        primaryjoin="Automaton.automaton_id == AutomatonTransition.automaton_id",
        foreign_keys="[AutomatonTransition.automaton_id]",
        back_populates="transitions",
    )
    event: Mapped["WorkflowEvent | None"] = relationship("WorkflowEvent")


# ==============================================================================
# Domain 2: Datasets, Cases & ML (Doc 08 §3 Member 2)
# ==============================================================================


class Dataset(Base):
    __tablename__ = "datasets"

    dataset_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("workflows.workflow_id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    source_kind: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # 'synthetic','uploaded','public_log'
    label_semantics: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # 'injected','none','external'
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    config_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "source_kind IN ('synthetic','uploaded','public_log')", name="chk_dataset_source_kind"
        ),
        CheckConstraint(
            "label_semantics IN ('injected','none','external')", name="chk_dataset_label_semantics"
        ),
    )

    workflow: Mapped["Workflow"] = relationship("Workflow", back_populates="datasets")
    cases: Mapped[list["Case"]] = relationship(
        "Case", back_populates="dataset", cascade="all, delete-orphan"
    )
    model_runs: Mapped[list["ModelRun"]] = relationship("ModelRun", back_populates="dataset")


class Case(Base):
    __tablename__ = "cases"

    case_pk: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    dataset_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("datasets.dataset_id", ondelete="CASCADE"), nullable=False
    )
    case_id: Mapped[str] = mapped_column(Text, nullable=False)
    label_class: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # 'normal','valid_variation','rule_violation','statistical_anomaly'
    anomaly_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    split: Mapped[str | None] = mapped_column(Text, nullable=True)  # 'train','val','test'

    __table_args__ = (
        UniqueConstraint("dataset_id", "case_id", name="uq_dataset_case_id"),
        CheckConstraint(
            "label_class IS NULL OR label_class IN ('normal','valid_variation','rule_violation','statistical_anomaly')",
            name="chk_case_label_class",
        ),
        CheckConstraint("split IS NULL OR split IN ('train','val','test')", name="chk_case_split"),
    )

    dataset: Mapped["Dataset"] = relationship("Dataset", back_populates="cases")
    events: Mapped[list["EventLog"]] = relationship(
        "EventLog", back_populates="case", cascade="all, delete-orphan"
    )
    fsm_results: Mapped[list["FsmResultModel"]] = relationship(
        "FsmResultModel", back_populates="case", cascade="all, delete-orphan"
    )
    ml_predictions: Mapped[list["MlPrediction"]] = relationship(
        "MlPrediction", back_populates="case", cascade="all, delete-orphan"
    )
    hybrid_decisions: Mapped[list["HybridDecisionModel"]] = relationship(
        "HybridDecisionModel", back_populates="case", cascade="all, delete-orphan"
    )


class EventLog(Base):
    __tablename__ = "event_log"

    case_pk: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("cases.case_pk", ondelete="CASCADE"),
        primary_key=True,
    )
    seq_index: Mapped[int] = mapped_column(Integer, primary_key=True)
    activity: Mapped[str] = mapped_column(Text, nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (Index("ix_event_ts", "ts"),)

    case: Mapped["Case"] = relationship("Case", back_populates="events")


class ModelRun(Base):
    __tablename__ = "model_runs"

    model_run_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("datasets.dataset_id"), nullable=False
    )
    detector: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # 'isolation_forest'|'markov'|'kmeans'|'random_forest'
    params: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    feature_spec_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    target_fpr: Mapped[float | None] = mapped_column(Float, nullable=True)
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    artifact: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    git_commit: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    dataset: Mapped["Dataset"] = relationship("Dataset", back_populates="model_runs")
    predictions: Mapped[list["MlPrediction"]] = relationship(
        "MlPrediction", back_populates="model_run", cascade="all, delete-orphan"
    )


class MlPrediction(Base):
    __tablename__ = "ml_predictions"

    prediction_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    case_pk: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("cases.case_pk", ondelete="CASCADE"),
        nullable=False,
    )
    model_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("model_runs.model_run_id", ondelete="CASCADE"), nullable=False
    )
    raw_score: Mapped[float] = mapped_column(Float, nullable=False)
    norm_score: Mapped[float] = mapped_column(Float, nullable=False)
    is_anomaly: Mapped[bool] = mapped_column(Boolean, nullable=False)
    factors: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("case_pk", "model_run_id", name="uq_case_model_run"),
        CheckConstraint(
            "norm_score >= 0.0 AND norm_score <= 1.0", name="chk_prediction_norm_score"
        ),
    )

    case: Mapped["Case"] = relationship("Case", back_populates="ml_predictions")
    model_run: Mapped["ModelRun"] = relationship("ModelRun", back_populates="predictions")


class FsmResultModel(Base):
    __tablename__ = "fsm_results"

    fsm_result_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    case_pk: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("cases.case_pk", ondelete="CASCADE"),
        nullable=False,
    )
    automaton_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("automata.automaton_id"), nullable=False
    )
    verdict: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # 'VALID_COMPLETE','VALID_PREFIX','INVALID'
    reason_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    fail_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fail_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    fail_event: Mapped[str | None] = mapped_column(Text, nullable=True)
    allowed_events: Mapped[list[str]] = mapped_column(StringList, default=list)
    state_path: Mapped[list[str]] = mapped_column(StringList, nullable=False)
    validated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("case_pk", "automaton_id", name="uq_case_automaton_result"),
        CheckConstraint(
            "verdict IN ('VALID_COMPLETE','VALID_PREFIX','INVALID')", name="chk_fsm_verdict"
        ),
    )

    case: Mapped["Case"] = relationship("Case", back_populates="fsm_results")
    automaton: Mapped["Automaton"] = relationship("Automaton")


# ==============================================================================
# Domain 3: Hybrid Decisions & Evaluations (Doc 08 §3 Member 3)
# ==============================================================================


class HybridDecisionModel(Base):
    __tablename__ = "hybrid_decisions"

    decision_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    case_pk: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("cases.case_pk", ondelete="CASCADE"),
        nullable=False,
    )
    fsm_result_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("fsm_results.fsm_result_id"),
        nullable=False,
    )
    ml_policy: Mapped[str] = mapped_column(Text, nullable=False)
    final_label: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # 'NORMAL','RULE_VIOLATION','STATISTICAL_ANOMALY','IN_PROGRESS'
    reason_code: Mapped[str] = mapped_column(Text, nullable=False)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "final_label IN ('NORMAL','RULE_VIOLATION','STATISTICAL_ANOMALY','IN_PROGRESS')",
            name="chk_final_label",
        ),
    )

    case: Mapped["Case"] = relationship("Case", back_populates="hybrid_decisions")
    fsm_result: Mapped["FsmResultModel"] = relationship("FsmResultModel")
    explanations: Mapped[list["ExplanationModel"]] = relationship(
        "ExplanationModel", back_populates="decision", cascade="all, delete-orphan"
    )


class DecisionMlEvidence(Base):
    __tablename__ = "decision_ml_evidence"

    decision_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("hybrid_decisions.decision_id", ondelete="CASCADE"),
        primary_key=True,
    )
    prediction_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("ml_predictions.prediction_id"),
        primary_key=True,
    )


class ExplanationModel(Base):
    __tablename__ = "explanations"

    explanation_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    decision_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("hybrid_decisions.decision_id", ondelete="CASCADE"),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # 'FSM','ISOLATION_FOREST','MARKOV','KMEANS','HYBRID'
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "source IN ('FSM','ISOLATION_FOREST','MARKOV','KMEANS','HYBRID')",
            name="chk_explanation_source",
        ),
    )

    decision: Mapped["HybridDecisionModel"] = relationship(
        "HybridDecisionModel", back_populates="explanations"
    )


class EvaluationRunModel(Base):
    __tablename__ = "evaluation_runs"

    eval_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("datasets.dataset_id"), nullable=False
    )
    detector: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # 'fsm_only','ml_only','hybrid', etc.
    split: Mapped[str] = mapped_column(Text, nullable=False)
    ml_policy: Mapped[str | None] = mapped_column(Text, nullable=True)
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    config_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    n_cases: Mapped[int] = mapped_column(Integer, nullable=False)
    base_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    tp: Mapped[int] = mapped_column(Integer, nullable=False)
    fp: Mapped[int] = mapped_column(Integer, nullable=False)
    tn: Mapped[int] = mapped_column(Integer, nullable=False)
    fn: Mapped[int] = mapped_column(Integer, nullable=False)
    fpr_valid_variation: Mapped[float | None] = mapped_column(Float, nullable=True)
    roc_auc: Mapped[float | None] = mapped_column(Float, nullable=True)
    pr_auc: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms_median: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms_p95: Mapped[float | None] = mapped_column(Float, nullable=True)
    hardware_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    dataset: Mapped["Dataset"] = relationship("Dataset")
    type_metrics: Mapped[list["EvaluationTypeMetricModel"]] = relationship(
        "EvaluationTypeMetricModel", back_populates="evaluation_run", cascade="all, delete-orphan"
    )


class EvaluationTypeMetricModel(Base):
    __tablename__ = "evaluation_type_metrics"

    eval_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("evaluation_runs.eval_id", ondelete="CASCADE"), primary_key=True
    )
    anomaly_type: Mapped[str] = mapped_column(Text, primary_key=True)
    n_cases: Mapped[int] = mapped_column(Integer, nullable=False)
    n_detected: Mapped[int] = mapped_column(Integer, nullable=False)

    evaluation_run: Mapped["EvaluationRunModel"] = relationship(
        "EvaluationRunModel", back_populates="type_metrics"
    )


# ==============================================================================
# Domain 4: Supplementary Packet Module (Doc 08 §3 Member 3)
# ==============================================================================


class PacketExperimentModel(Base):
    __tablename__ = "packet_experiments"

    experiment_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    source_description: Mapped[str] = mapped_column(Text, nullable=False)
    pcap_sha256: Mapped[str | None] = mapped_column(Text, nullable=True)
    snaplen: Mapped[int | None] = mapped_column(Integer, nullable=True)
    profile: Mapped[str] = mapped_column(Text, nullable=False)  # 'strict','tolerant'
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    __table_args__ = (
        CheckConstraint("profile IN ('strict','tolerant')", name="chk_packet_profile"),
    )

    flows: Mapped[list["PacketFlowModel"]] = relationship(
        "PacketFlowModel", back_populates="experiment", cascade="all, delete-orphan"
    )


class PacketFlowModel(Base):
    __tablename__ = "packet_flows"

    flow_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    experiment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("packet_experiments.experiment_id", ondelete="CASCADE"), nullable=False
    )
    src_ip: Mapped[str | None] = mapped_column(Text, nullable=True)
    src_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dst_ip: Mapped[str | None] = mapped_column(Text, nullable=True)
    dst_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    n_events: Mapped[int] = mapped_column(Integer, nullable=False)
    verdict: Mapped[str] = mapped_column(Text, nullable=False)
    fail_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fail_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    fail_event: Mapped[str | None] = mapped_column(Text, nullable=True)
    scenario: Mapped[str | None] = mapped_column(Text, nullable=True)
    intended_verdict: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "verdict IN ('ACCEPTED_CLEAN','ACCEPTED_RESET','INCOMPLETE','INVALID','MIDSTREAM')",
            name="chk_flow_verdict",
        ),
    )

    experiment: Mapped["PacketExperimentModel"] = relationship(
        "PacketExperimentModel", back_populates="flows"
    )
    events: Mapped[list["PacketEventModel"]] = relationship(
        "PacketEventModel", back_populates="flow", cascade="all, delete-orphan"
    )


class PacketEventModel(Base):
    __tablename__ = "packet_events"

    flow_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("packet_flows.flow_id", ondelete="CASCADE"),
        primary_key=True,
    )
    seq_index: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    direction: Mapped[str | None] = mapped_column(Text, nullable=True)  # 'C2S','S2C'
    ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "direction IS NULL OR direction IN ('C2S','S2C')", name="chk_packet_direction"
        ),
    )

    flow: Mapped["PacketFlowModel"] = relationship("PacketFlowModel", back_populates="events")
