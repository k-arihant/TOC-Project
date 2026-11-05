"""Supplementary Packet Validation schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class PacketExperimentResponse(BaseModel):
    experiment_id: int
    name: str
    source_description: str
    pcap_sha256: Optional[str] = None
    profile: str
    notes: Optional[str] = None
    flow_count: int = 0
    created_at: datetime


class PacketFlowResponse(BaseModel):
    flow_id: int
    experiment_id: int
    src_ip: Optional[str] = None
    src_port: Optional[int] = None
    dst_ip: Optional[str] = None
    dst_port: Optional[int] = None
    start_ts: Optional[datetime] = None
    n_events: int
    verdict: str
    scenario: Optional[str] = None
    intended_verdict: Optional[str] = None


class PacketEventResponse(BaseModel):
    seq_index: int
    symbol: str
    direction: Optional[str] = None
    ts: Optional[datetime] = None


class PacketFlowDetailResponse(BaseModel):
    flow: PacketFlowResponse
    events: list[PacketEventResponse] = []
