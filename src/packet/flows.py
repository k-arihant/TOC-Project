from collections.abc import Iterable
from dataclasses import dataclass, field

from src.packet.mapper import FLAG_ACK, FLAG_FIN, FLAG_RST, FLAG_SYN
from src.packet.reader import PacketRecord


@dataclass
class Flow:
    flow_id: str
    src_endpoint: tuple[str, int]  # (ip, port) of initiator
    dst_endpoint: tuple[str, int]  # (ip, port) of responder
    records: list[PacketRecord] = field(default_factory=list)
    is_midstream: bool = False
    scenario: str | None = None

    @property
    def n_packets(self) -> int:
        return len(self.records)


def _canonical_key(
    ep1: tuple[str, int], ep2: tuple[str, int]
) -> tuple[tuple[str, int], tuple[str, int]]:
    return tuple(sorted([ep1, ep2]))  # type: ignore[return-value]


def build_flows(records: Iterable[PacketRecord]) -> list[Flow]:
    """
    Reconstruct bidirectional TCP flows from packet stream per Doc 07 §3.2.

    Rules:
    - Bidirectional 5-tuple canonical key.
    - Initiator is the sender of the first SYN packet.
    - Mid-stream flows (first packet is not a clean SYN) are marked is_midstream=True.
    - Port reuse: if a flow has seen a terminating event (RST or completed teardown)
      and a new SYN arrives, a new flow instance is created.

    Args:
        records: Iterable of PacketRecord objects.

    Returns:
        list[Flow]: Reconstructed TCP flows.
    """
    # Map from canonical 5-tuple key to active flow
    active_flows: dict[tuple[tuple[str, int], tuple[str, int]], Flow] = {}
    completed_flows: list[Flow] = []
    flow_counters: dict[tuple[tuple[str, int], tuple[str, int]], int] = {}

    for rec in records:
        ep_src = (rec.src_ip, rec.src_port)
        ep_dst = (rec.dst_ip, rec.dst_port)
        key = _canonical_key(ep_src, ep_dst)

        flags = rec.tcp_flags
        is_syn = bool(flags & FLAG_SYN)
        is_ack = bool(flags & FLAG_ACK)
        is_rst = bool(flags & FLAG_RST)
        is_clean_syn = is_syn and not is_ack

        current_flow = active_flows.get(key)

        # Check for port reuse: flow was active but a new clean SYN arrives
        if current_flow is not None and is_clean_syn:
            # Check if current flow already saw termination or data exchange
            saw_rst = any(bool(r.tcp_flags & FLAG_RST) for r in current_flow.records)
            saw_fin = any(bool(r.tcp_flags & FLAG_FIN) for r in current_flow.records)
            if saw_rst or saw_fin:
                # Finalize current flow and start a new one
                completed_flows.append(current_flow)
                current_flow = None

        if current_flow is None:
            # New flow
            count = flow_counters.get(key, 0) + 1
            flow_counters[key] = count
            flow_id = f"flow_{key[0][0]}:{key[0][1]}_{key[1][0]}:{key[1][1]}_{count}"

            if is_clean_syn:
                # Initiator is sender of first SYN
                flow = Flow(
                    flow_id=flow_id,
                    src_endpoint=ep_src,
                    dst_endpoint=ep_dst,
                    records=[rec],
                    is_midstream=False,
                )
            else:
                # Midstream start
                flow = Flow(
                    flow_id=flow_id,
                    src_endpoint=ep_src,
                    dst_endpoint=ep_dst,
                    records=[rec],
                    is_midstream=True,
                )
            active_flows[key] = flow
        else:
            current_flow.records.append(rec)
            if is_rst:
                # Flow terminated by RST
                completed_flows.append(current_flow)
                del active_flows[key]

    # Add any remaining active flows to completed
    completed_flows.extend(active_flows.values())

    return completed_flows
