"""Supplementary Packet Validation router."""

import hashlib
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from src.api.schemas.packet import (
    PacketEventResponse,
    PacketExperimentResponse,
    PacketFlowDetailResponse,
    PacketFlowResponse,
)
from src.common.config import settings
from src.db.repositories.packet_repo import PacketRepository
from src.db.session import get_db
from src.packet.flows import build_flows
from src.packet.mapper import to_events
from src.packet.reader import read_packets
from src.packet.tcp_fsm import load_tcp_dfa

router = APIRouter(prefix="/packet", tags=["Packet Validation"])


@router.post("/experiments", response_model=PacketExperimentResponse, status_code=status.HTTP_201_CREATED)
def upload_pcap_experiment(
    name: str = Form(...),
    source_description: str = Form(...),
    profile: str = Form("strict", pattern="^(strict|tolerant)$"),
    notes: Optional[str] = Form(None),
    pcap_file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> PacketExperimentResponse:
    """Upload PCAP file, slice bidirectional flows, and run formal TCP FSM validation."""
    contents = pcap_file.file.read()
    file_size_mb = len(contents) / (1024 * 1024)
    if file_size_mb > settings.PACKET_MAX_MB:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "code": "FILE_TOO_LARGE",
                "message": f"PCAP file exceeds max size of {settings.PACKET_MAX_MB}MB",
            },
        )

    pcap_sha256 = hashlib.sha256(contents).hexdigest()

    # Save to temp file for streaming Scapy reader
    with tempfile.NamedTemporaryFile(suffix=".pcap", delete=False) as tmp:
        tmp.write(contents)
        tmp_path = Path(tmp.name)

    try:
        packets = list(read_packets(tmp_path, max_packets=settings.PACKET_MAX_PACKETS))
        flows = build_flows(packets)

        tcp_dfa = load_tcp_dfa(profile=profile)
        flows_data = []

        for flow in flows:
            symbols = to_events(flow)
            verdict = "ACCEPTED_CLEAN" if tcp_dfa.accepts(symbols) else "INVALID"
            flows_data.append(
                {
                    "src_ip": flow.src_endpoint[0],
                    "src_port": flow.src_endpoint[1],
                    "dst_ip": flow.dst_endpoint[0],
                    "dst_port": flow.dst_endpoint[1],
                    "n_events": len(symbols),
                    "verdict": verdict,
                    "events": symbols,
                }
            )

        p_repo = PacketRepository(db)
        exp = p_repo.create_experiment(
            name=name,
            source_description=source_description,
            profile=profile,
            pcap_sha256=pcap_sha256,
            snaplen=None,
            notes=notes,
        )
        p_repo.record_flows(exp.experiment_id, flows_data)

        return PacketExperimentResponse(
            experiment_id=exp.experiment_id,
            name=exp.name,
            source_description=exp.source_description,
            pcap_sha256=exp.pcap_sha256,
            profile=exp.profile,
            notes=exp.notes,
            flow_count=len(flows_data),
            created_at=exp.created_at,
        )
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


@router.get("/experiments", response_model=list[PacketExperimentResponse])
def list_packet_experiments(db: Session = Depends(get_db)) -> list[PacketExperimentResponse]:
    """List all packet validation experiments."""
    p_repo = PacketRepository(db)
    experiments = p_repo.list_experiments()
    return [
        PacketExperimentResponse(
            experiment_id=e.experiment_id,
            name=e.name,
            source_description=e.source_description,
            pcap_sha256=e.pcap_sha256,
            profile=e.profile,
            notes=e.notes,
            flow_count=len(e.flows),
            created_at=e.created_at,
        )
        for e in experiments
    ]


@router.get("/experiments/{id}", response_model=PacketExperimentResponse)
def get_packet_experiment(id: int, db: Session = Depends(get_db)) -> PacketExperimentResponse:
    """Retrieve details for a specific packet experiment."""
    p_repo = PacketRepository(db)
    e = p_repo.get_experiment(id)
    if not e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "EXPERIMENT_NOT_FOUND", "message": f"Packet experiment {id} not found"},
        )
    return PacketExperimentResponse(
        experiment_id=e.experiment_id,
        name=e.name,
        source_description=e.source_description,
        pcap_sha256=e.pcap_sha256,
        profile=e.profile,
        notes=e.notes,
        flow_count=len(e.flows),
        created_at=e.created_at,
    )


@router.get("/experiments/{id}/flows", response_model=list[PacketFlowDetailResponse])
def get_experiment_flows(id: int, db: Session = Depends(get_db)) -> list[PacketFlowDetailResponse]:
    """Retrieve all sliced flows and their verdicts for a packet experiment."""
    p_repo = PacketRepository(db)
    flows = p_repo.get_flows_for_experiment(id)
    results = []
    for f in flows:
        events = [
            PacketEventResponse(
                seq_index=ev.seq_index,
                symbol=ev.symbol,
                direction=ev.direction,
                ts=ev.ts,
            )
            for ev in sorted(f.events, key=lambda x: x.seq_index)
        ]
        flow_resp = PacketFlowResponse(
            flow_id=f.flow_id,
            experiment_id=f.experiment_id,
            src_ip=f.src_ip,
            src_port=f.src_port,
            dst_ip=f.dst_ip,
            dst_port=f.dst_port,
            start_ts=f.start_ts,
            n_events=f.n_events,
            verdict=f.verdict,
            scenario=f.scenario,
            intended_verdict=f.intended_verdict,
        )
        results.append(PacketFlowDetailResponse(flow=flow_resp, events=events))
    return results
