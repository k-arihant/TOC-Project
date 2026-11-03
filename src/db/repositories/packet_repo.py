from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import PacketEventModel, PacketExperimentModel, PacketFlowModel


class PacketRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_experiment(
        self,
        name: str,
        source_description: str,
        profile: str,
        pcap_sha256: str | None = None,
        snaplen: int | None = None,
        notes: str | None = None,
    ) -> PacketExperimentModel:
        exp = PacketExperimentModel(
            name=name,
            source_description=source_description,
            profile=profile,
            pcap_sha256=pcap_sha256,
            snaplen=snaplen,
            notes=notes,
        )
        self.db.add(exp)
        self.db.commit()
        self.db.refresh(exp)
        return exp

    def get_experiment(self, experiment_id: int) -> PacketExperimentModel | None:
        stmt = select(PacketExperimentModel).where(
            PacketExperimentModel.experiment_id == experiment_id
        )
        return self.db.scalars(stmt).first()

    def list_experiments(self) -> list[PacketExperimentModel]:
        stmt = select(PacketExperimentModel).order_by(PacketExperimentModel.experiment_id)
        return list(self.db.scalars(stmt).all())

    def record_flows(
        self,
        experiment_id: int,
        flows_data: list[dict],
    ) -> list[PacketFlowModel]:
        flow_models: list[PacketFlowModel] = []
        for fd in flows_data:
            flow_obj = PacketFlowModel(
                experiment_id=experiment_id,
                src_ip=fd.get("src_ip"),
                src_port=fd.get("src_port"),
                dst_ip=fd.get("dst_ip"),
                dst_port=fd.get("dst_port"),
                n_events=fd.get("n_events", 0),
                verdict=fd["verdict"],
                fail_index=fd.get("fail_index"),
                fail_state=fd.get("fail_state"),
                fail_event=fd.get("fail_event"),
                scenario=fd.get("scenario"),
                intended_verdict=fd.get("intended_verdict"),
            )
            self.db.add(flow_obj)
            self.db.flush()

            events = fd.get("events", [])
            for seq_idx, symbol in enumerate(events):
                ev = PacketEventModel(
                    flow_id=flow_obj.flow_id,
                    seq_index=seq_idx,
                    symbol=symbol,
                )
                self.db.add(ev)
            flow_models.append(flow_obj)

        self.db.commit()
        return flow_models

    def get_flows_for_experiment(self, experiment_id: int) -> list[PacketFlowModel]:
        stmt = (
            select(PacketFlowModel)
            .where(PacketFlowModel.experiment_id == experiment_id)
            .order_by(PacketFlowModel.flow_id)
        )
        return list(self.db.scalars(stmt).all())
