from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.common.types import FsmResult, HybridDecision
from src.db.models import (
    Case,
    DecisionMlEvidence,
    ExplanationModel,
    FsmResultModel,
    HybridDecisionModel,
)


class HybridRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record_fsm_result(
        self,
        case_pk: int,
        automaton_id: int,
        result: FsmResult,
    ) -> FsmResultModel:
        fsm_obj = FsmResultModel(
            case_pk=case_pk,
            automaton_id=automaton_id,
            verdict=result.verdict.value,
            reason_code=result.reason_code,
            fail_index=result.fail_index,
            fail_state=result.fail_state,
            fail_event=result.fail_event,
            allowed_events=result.allowed_events or [],
            state_path=result.state_path,
        )
        self.db.add(fsm_obj)
        self.db.commit()
        self.db.refresh(fsm_obj)
        return fsm_obj

    def get_fsm_result(self, fsm_result_id: int) -> FsmResultModel | None:
        stmt = select(FsmResultModel).where(FsmResultModel.fsm_result_id == fsm_result_id)
        return self.db.scalars(stmt).first()

    def record_decision(
        self,
        case_pk: int,
        fsm_result_id: int,
        decision: HybridDecision,
        ml_policy: str = "any",
        reason_code: str = "HYBRID_FUSION",
        prediction_ids: list[int] | None = None,
    ) -> HybridDecisionModel:
        dec_obj = HybridDecisionModel(
            case_pk=case_pk,
            fsm_result_id=fsm_result_id,
            ml_policy=ml_policy,
            final_label=decision.final_label.value,
            reason_code=reason_code,
        )
        self.db.add(dec_obj)
        self.db.flush()

        # Link ML evidence
        if prediction_ids:
            for pid in prediction_ids:
                ev = DecisionMlEvidence(decision_id=dec_obj.decision_id, prediction_id=pid)
                self.db.add(ev)

        # Store explanations
        for rank, text in enumerate(decision.explanation):
            exp = ExplanationModel(
                decision_id=dec_obj.decision_id,
                source="HYBRID",
                rank=rank,
                text=text,
                detail={},
            )
            self.db.add(exp)

        self.db.commit()
        self.db.refresh(dec_obj)
        return dec_obj

    def get_decision(self, decision_id: int) -> HybridDecisionModel | None:
        stmt = select(HybridDecisionModel).where(HybridDecisionModel.decision_id == decision_id)
        return self.db.scalars(stmt).first()

    def get_decision_by_case(self, case_pk: int) -> HybridDecisionModel | None:
        stmt = select(HybridDecisionModel).where(HybridDecisionModel.case_pk == case_pk)
        return self.db.scalars(stmt).first()

    def list_decisions(
        self,
        dataset_id: int | None = None,
        final_label: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[HybridDecisionModel], int]:
        stmt = select(HybridDecisionModel)
        if dataset_id or final_label:
            stmt = stmt.join(HybridDecisionModel.case)
            if dataset_id:
                stmt = stmt.where(Case.dataset_id == dataset_id)
            if final_label:
                stmt = stmt.where(HybridDecisionModel.final_label == final_label)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.scalar(count_stmt) or 0

        offset = (page - 1) * page_size
        stmt = stmt.order_by(HybridDecisionModel.decision_id.desc()).offset(offset).limit(page_size)
        items = list(self.db.scalars(stmt).all())
        return items, total
