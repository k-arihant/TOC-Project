from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import EvaluationRunModel, EvaluationTypeMetricModel


class EvaluationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_evaluation_run(
        self,
        dataset_id: int,
        detector: str,
        split: str,
        n_cases: int,
        tp: int,
        fp: int,
        tn: int,
        fn: int,
        ml_policy: str | None = None,
        seed: int | None = None,
        config_hash: str | None = None,
        base_rate: float | None = None,
        fpr_valid_variation: float | None = None,
        roc_auc: float | None = None,
        pr_auc: float | None = None,
        latency_ms_median: float | None = None,
        latency_ms_p95: float | None = None,
        hardware_note: str | None = None,
        type_metrics: dict[str, dict[str, int]] | None = None,
    ) -> EvaluationRunModel:
        run = EvaluationRunModel(
            dataset_id=dataset_id,
            detector=detector,
            split=split,
            ml_policy=ml_policy,
            seed=seed,
            config_hash=config_hash,
            n_cases=n_cases,
            base_rate=base_rate,
            tp=tp,
            fp=fp,
            tn=tn,
            fn=fn,
            fpr_valid_variation=fpr_valid_variation,
            roc_auc=roc_auc,
            pr_auc=pr_auc,
            latency_ms_median=latency_ms_median,
            latency_ms_p95=latency_ms_p95,
            hardware_note=hardware_note,
        )
        self.db.add(run)
        self.db.flush()

        if type_metrics:
            for atype, counts in type_metrics.items():
                metric = EvaluationTypeMetricModel(
                    eval_id=run.eval_id,
                    anomaly_type=atype,
                    n_cases=counts.get("n_cases", 0),
                    n_detected=counts.get("n_detected", 0),
                )
                self.db.add(metric)

        self.db.commit()
        self.db.refresh(run)
        return run

    def get_evaluation_run(self, eval_id: int) -> EvaluationRunModel | None:
        stmt = select(EvaluationRunModel).where(EvaluationRunModel.eval_id == eval_id)
        return self.db.scalars(stmt).first()

    def list_evaluation_runs(self, dataset_id: int | None = None) -> list[EvaluationRunModel]:
        stmt = select(EvaluationRunModel)
        if dataset_id:
            stmt = stmt.where(EvaluationRunModel.dataset_id == dataset_id)
        stmt = stmt.order_by(EvaluationRunModel.eval_id)
        return list(self.db.scalars(stmt).all())
