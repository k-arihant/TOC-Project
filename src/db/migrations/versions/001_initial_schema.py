"""Initial schema migration across all domains.

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-11-03 12:00:00.000000

"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Workflows
    op.create_table(
        "workflows",
        sa.Column("workflow_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("name", "version", name="uq_workflow_name_version"),
    )

    # 2. Workflow Events
    op.create_table(
        "workflow_events",
        sa.Column("event_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "workflow_id",
            sa.Integer(),
            sa.ForeignKey("workflows.workflow_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.UniqueConstraint("workflow_id", "code", name="uq_wf_code"),
        sa.UniqueConstraint("workflow_id", "name", name="uq_wf_name"),
    )

    # 3. Automata
    op.create_table(
        "automata",
        sa.Column("automaton_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "workflow_id",
            sa.Integer(),
            sa.ForeignKey("workflows.workflow_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column(
            "derived_from", sa.Integer(), sa.ForeignKey("automata.automaton_id"), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('DFA','NFA','MIN_DFA','BOUNDED_DFA')", name="chk_automaton_kind"
        ),
    )

    # 4. Automaton States
    op.create_table(
        "automaton_states",
        sa.Column(
            "automaton_id",
            sa.Integer(),
            sa.ForeignKey("automata.automaton_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("state_name", sa.Text(), primary_key=True),
        sa.Column("is_initial", sa.Boolean(), nullable=False, default=False),
        sa.Column("is_accepting", sa.Boolean(), nullable=False, default=False),
        sa.Column("is_dead", sa.Boolean(), nullable=False, default=False),
        sa.Column("merged_from", sa.JSON(), nullable=True),
    )

    # 5. Automaton Transitions
    op.create_table(
        "automaton_transitions",
        sa.Column("transition_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("automaton_id", sa.Integer(), nullable=False),
        sa.Column("from_state", sa.Text(), nullable=False),
        sa.Column(
            "event_id", sa.Integer(), sa.ForeignKey("workflow_events.event_id"), nullable=True
        ),
        sa.Column("to_state", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["automaton_id", "from_state"],
            ["automaton_states.automaton_id", "automaton_states.state_name"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["automaton_id", "to_state"],
            ["automaton_states.automaton_id", "automaton_states.state_name"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "automaton_id", "from_state", "event_id", name="uq_automaton_transition"
        ),
    )

    # 6. Datasets
    op.create_table(
        "datasets",
        sa.Column("dataset_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "workflow_id", sa.Integer(), sa.ForeignKey("workflows.workflow_id"), nullable=False
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("source_kind", sa.Text(), nullable=False),
        sa.Column("label_semantics", sa.Text(), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=True),
        sa.Column("config_hash", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "source_kind IN ('synthetic','uploaded','public_log')", name="chk_dataset_source_kind"
        ),
        sa.CheckConstraint(
            "label_semantics IN ('injected','none','external')", name="chk_dataset_label_semantics"
        ),
    )

    # 7. Cases
    op.create_table(
        "cases",
        sa.Column(
            "case_pk",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "dataset_id",
            sa.Integer(),
            sa.ForeignKey("datasets.dataset_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("case_id", sa.Text(), nullable=False),
        sa.Column("label_class", sa.Text(), nullable=True),
        sa.Column("anomaly_type", sa.Text(), nullable=True),
        sa.Column("split", sa.Text(), nullable=True),
        sa.UniqueConstraint("dataset_id", "case_id", name="uq_dataset_case_id"),
        sa.CheckConstraint(
            "label_class IS NULL OR label_class IN ('normal','valid_variation','rule_violation','statistical_anomaly')",
            name="chk_case_label_class",
        ),
        sa.CheckConstraint(
            "split IS NULL OR split IN ('train','val','test')", name="chk_case_split"
        ),
    )

    # 8. Event Log
    op.create_table(
        "event_log",
        sa.Column(
            "case_pk",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            sa.ForeignKey("cases.case_pk", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("seq_index", sa.Integer(), primary_key=True),
        sa.Column("activity", sa.Text(), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attributes", sa.JSON(), nullable=False, default=dict),
    )
    op.create_index("ix_event_ts", "event_log", ["ts"])

    # 9. Model Runs
    op.create_table(
        "model_runs",
        sa.Column("model_run_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("datasets.dataset_id"), nullable=False),
        sa.Column("detector", sa.Text(), nullable=False),
        sa.Column("params", sa.JSON(), nullable=False, default=dict),
        sa.Column("feature_spec_version", sa.Text(), nullable=True),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("target_fpr", sa.Float(), nullable=True),
        sa.Column("threshold", sa.Float(), nullable=True),
        sa.Column("artifact", sa.LargeBinary(), nullable=True),
        sa.Column("git_commit", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 10. ML Predictions
    op.create_table(
        "ml_predictions",
        sa.Column(
            "prediction_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "case_pk",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            sa.ForeignKey("cases.case_pk", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "model_run_id",
            sa.Integer(),
            sa.ForeignKey("model_runs.model_run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("raw_score", sa.Float(), nullable=False),
        sa.Column("norm_score", sa.Float(), nullable=False),
        sa.Column("is_anomaly", sa.Boolean(), nullable=False),
        sa.Column("factors", sa.JSON(), nullable=False, default=list),
        sa.Column("scored_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("case_pk", "model_run_id", name="uq_case_model_run"),
        sa.CheckConstraint(
            "norm_score >= 0.0 AND norm_score <= 1.0", name="chk_prediction_norm_score"
        ),
    )

    # 11. FSM Results
    op.create_table(
        "fsm_results",
        sa.Column(
            "fsm_result_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "case_pk",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            sa.ForeignKey("cases.case_pk", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "automaton_id", sa.Integer(), sa.ForeignKey("automata.automaton_id"), nullable=False
        ),
        sa.Column("verdict", sa.Text(), nullable=False),
        sa.Column("reason_code", sa.Text(), nullable=True),
        sa.Column("fail_index", sa.Integer(), nullable=True),
        sa.Column("fail_state", sa.Text(), nullable=True),
        sa.Column("fail_event", sa.Text(), nullable=True),
        sa.Column("allowed_events", sa.JSON(), nullable=True),
        sa.Column("state_path", sa.JSON(), nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("case_pk", "automaton_id", name="uq_case_automaton_result"),
        sa.CheckConstraint(
            "verdict IN ('VALID_COMPLETE','VALID_PREFIX','INVALID')", name="chk_fsm_verdict"
        ),
    )

    # 12. Hybrid Decisions
    op.create_table(
        "hybrid_decisions",
        sa.Column(
            "decision_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "case_pk",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            sa.ForeignKey("cases.case_pk", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "fsm_result_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            sa.ForeignKey("fsm_results.fsm_result_id"),
            nullable=False,
        ),
        sa.Column("ml_policy", sa.Text(), nullable=False),
        sa.Column("final_label", sa.Text(), nullable=False),
        sa.Column("reason_code", sa.Text(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "final_label IN ('NORMAL','RULE_VIOLATION','STATISTICAL_ANOMALY','IN_PROGRESS')",
            name="chk_final_label",
        ),
    )

    # 13. Decision ML Evidence
    op.create_table(
        "decision_ml_evidence",
        sa.Column(
            "decision_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            sa.ForeignKey("hybrid_decisions.decision_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "prediction_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            sa.ForeignKey("ml_predictions.prediction_id"),
            primary_key=True,
        ),
    )

    # 14. Explanations
    op.create_table(
        "explanations",
        sa.Column(
            "explanation_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "decision_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            sa.ForeignKey("hybrid_decisions.decision_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False, default=dict),
        sa.CheckConstraint(
            "source IN ('FSM','ISOLATION_FOREST','MARKOV','KMEANS','HYBRID')",
            name="chk_explanation_source",
        ),
    )

    # 15. Evaluation Runs
    op.create_table(
        "evaluation_runs",
        sa.Column("eval_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("datasets.dataset_id"), nullable=False),
        sa.Column("detector", sa.Text(), nullable=False),
        sa.Column("split", sa.Text(), nullable=False),
        sa.Column("ml_policy", sa.Text(), nullable=True),
        sa.Column("seed", sa.Integer(), nullable=True),
        sa.Column("config_hash", sa.Text(), nullable=True),
        sa.Column("n_cases", sa.Integer(), nullable=False),
        sa.Column("base_rate", sa.Float(), nullable=True),
        sa.Column("tp", sa.Integer(), nullable=False),
        sa.Column("fp", sa.Integer(), nullable=False),
        sa.Column("tn", sa.Integer(), nullable=False),
        sa.Column("fn", sa.Integer(), nullable=False),
        sa.Column("fpr_valid_variation", sa.Float(), nullable=True),
        sa.Column("roc_auc", sa.Float(), nullable=True),
        sa.Column("pr_auc", sa.Float(), nullable=True),
        sa.Column("latency_ms_median", sa.Float(), nullable=True),
        sa.Column("latency_ms_p95", sa.Float(), nullable=True),
        sa.Column("hardware_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 16. Evaluation Type Metrics
    op.create_table(
        "evaluation_type_metrics",
        sa.Column(
            "eval_id",
            sa.Integer(),
            sa.ForeignKey("evaluation_runs.eval_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("anomaly_type", sa.Text(), primary_key=True),
        sa.Column("n_cases", sa.Integer(), nullable=False),
        sa.Column("n_detected", sa.Integer(), nullable=False),
    )

    # 17. Packet Experiments
    op.create_table(
        "packet_experiments",
        sa.Column("experiment_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("source_description", sa.Text(), nullable=False),
        sa.Column("pcap_sha256", sa.Text(), nullable=True),
        sa.Column("snaplen", sa.Integer(), nullable=True),
        sa.Column("profile", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("profile IN ('strict','tolerant')", name="chk_packet_profile"),
    )

    # 18. Packet Flows
    op.create_table(
        "packet_flows",
        sa.Column(
            "flow_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "experiment_id",
            sa.Integer(),
            sa.ForeignKey("packet_experiments.experiment_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("src_ip", sa.Text(), nullable=True),
        sa.Column("src_port", sa.Integer(), nullable=True),
        sa.Column("dst_ip", sa.Text(), nullable=True),
        sa.Column("dst_port", sa.Integer(), nullable=True),
        sa.Column("start_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column("n_events", sa.Integer(), nullable=False),
        sa.Column("verdict", sa.Text(), nullable=False),
        sa.Column("fail_index", sa.Integer(), nullable=True),
        sa.Column("fail_state", sa.Text(), nullable=True),
        sa.Column("fail_event", sa.Text(), nullable=True),
        sa.Column("scenario", sa.Text(), nullable=True),
        sa.Column("intended_verdict", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "verdict IN ('ACCEPTED_CLEAN','ACCEPTED_RESET','INCOMPLETE','INVALID','MIDSTREAM')",
            name="chk_flow_verdict",
        ),
    )

    # 19. Packet Events
    op.create_table(
        "packet_events",
        sa.Column(
            "flow_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            sa.ForeignKey("packet_flows.flow_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("seq_index", sa.Integer(), primary_key=True),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("direction", sa.Text(), nullable=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "direction IS NULL OR direction IN ('C2S','S2C')", name="chk_packet_direction"
        ),
    )


def downgrade() -> None:
    op.drop_table("packet_events")
    op.drop_table("packet_flows")
    op.drop_table("packet_experiments")
    op.drop_table("evaluation_type_metrics")
    op.drop_table("evaluation_runs")
    op.drop_table("explanations")
    op.drop_table("decision_ml_evidence")
    op.drop_table("hybrid_decisions")
    op.drop_table("fsm_results")
    op.drop_table("ml_predictions")
    op.drop_table("model_runs")
    op.drop_table("event_log")
    op.drop_table("cases")
    op.drop_table("datasets")
    op.drop_table("automaton_transitions")
    op.drop_table("automaton_states")
    op.drop_table("automata")
    op.drop_table("workflow_events")
    op.drop_table("workflows")
