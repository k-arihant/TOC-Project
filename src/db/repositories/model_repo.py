from sqlalchemy import select
from sqlalchemy.orm import Session

from src.common.types import DetectorScore
from src.db.models import MlPrediction, ModelRun


class ModelRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_model_run(
        self,
        dataset_id: int,
        detector: str,
        params: dict,
        seed: int,
        feature_spec_version: str | None = None,
        target_fpr: float | None = None,
        threshold: float | None = None,
        artifact: bytes | None = None,
        git_commit: str | None = None,
    ) -> ModelRun:
        run = ModelRun(
            dataset_id=dataset_id,
            detector=detector,
            params=params,
            seed=seed,
            feature_spec_version=feature_spec_version,
            target_fpr=target_fpr,
            threshold=threshold,
            artifact=artifact,
            git_commit=git_commit,
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def get_model_run(self, model_run_id: int) -> ModelRun | None:
        stmt = select(ModelRun).where(ModelRun.model_run_id == model_run_id)
        return self.db.scalars(stmt).first()

    def list_model_runs(self, dataset_id: int | None = None) -> list[ModelRun]:
        stmt = select(ModelRun)
        if dataset_id:
            stmt = stmt.where(ModelRun.dataset_id == dataset_id)
        stmt = stmt.order_by(ModelRun.model_run_id)
        return list(self.db.scalars(stmt).all())

    def record_prediction(
        self,
        case_pk: int,
        model_run_id: int,
        score: DetectorScore,
    ) -> MlPrediction:
        factors_data = [
            {
                "name": f.name,
                "value": f.value,
                "reference": f.reference,
                "note": f.note,
            }
            for f in score.factors
        ]
        pred = MlPrediction(
            case_pk=case_pk,
            model_run_id=model_run_id,
            raw_score=score.raw_score,
            norm_score=score.norm_score,
            is_anomaly=score.is_anomaly,
            factors=factors_data,
        )
        self.db.add(pred)
        self.db.commit()
        self.db.refresh(pred)
        return pred

    def get_predictions_by_case(self, case_pk: int) -> list[MlPrediction]:
        stmt = (
            select(MlPrediction)
            .where(MlPrediction.case_pk == case_pk)
            .order_by(MlPrediction.model_run_id)
        )
        return list(self.db.scalars(stmt).all())
