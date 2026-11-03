from src.packet.flows import build_flows
from src.packet.mapper import FLAG_ACK, FLAG_FIN, FLAG_RST, FLAG_SYN
from src.packet.reader import PacketRecord


def make_pkt(
    idx: int,
    flags: int,
    is_response: bool = False,
    src_port: int = 50000,
    dst_port: int = 80,
    payload_len: int = 0,
) -> PacketRecord:
    src_ip, dst_ip = ("10.0.0.2", "10.0.0.1") if is_response else ("10.0.0.1", "10.0.0.2")
    sport, dport = (dst_port, src_port) if is_response else (src_port, dst_port)
    return PacketRecord(
        timestamp=1000.0 + idx,
        src_ip=src_ip,
        dst_ip=dst_ip,
        src_port=sport,
        dst_port=dport,
        tcp_flags=flags,
        payload_len=payload_len,
        packet_idx=idx,
    )


def test_flows_clean_handshake():
    packets = [
        make_pkt(0, FLAG_SYN),
        make_pkt(1, FLAG_SYN | FLAG_ACK, is_response=True),
        make_pkt(2, FLAG_ACK),
    ]
    flows = build_flows(packets)

    assert len(flows) == 1
    flow = flows[0]
    assert flow.is_midstream is False
    assert flow.src_endpoint == ("10.0.0.1", 50000)
    assert flow.dst_endpoint == ("10.0.0.2", 80)
    assert flow.n_packets == 3


def test_flows_midstream_start():
    # Capture starts with an ACK (no initial SYN)
    packets = [
        make_pkt(0, FLAG_ACK),
        make_pkt(1, FLAG_ACK, is_response=True, payload_len=50),
    ]
    flows = build_flows(packets)

    assert len(flows) == 1
    assert flows[0].is_midstream is True


def test_flows_port_reuse_after_rst():
    packets = [
        # First connection terminated by RST
        make_pkt(0, FLAG_SYN),
        make_pkt(1, FLAG_RST, is_response=True),
        # Reused port with a new SYN
        make_pkt(2, FLAG_SYN),
        make_pkt(3, FLAG_SYN | FLAG_ACK, is_response=True),
    ]
    flows = build_flows(packets)

    assert len(flows) == 2
    assert flows[0].n_packets == 2
    assert flows[1].n_packets == 2
    assert flows[0].flow_id != flows[1].flow_id


def test_flows_port_reuse_after_fin():
    packets = [
        # First connection finished
        make_pkt(0, FLAG_SYN),
        make_pkt(1, FLAG_SYN | FLAG_ACK, is_response=True),
        make_pkt(2, FLAG_FIN),
        # New connection on same 5-tuple
        make_pkt(3, FLAG_SYN),
        make_pkt(4, FLAG_SYN | FLAG_ACK, is_response=True),
    ]
    flows = build_flows(packets)

    assert len(flows) == 2
    assert flows[0].is_midstream is False
    assert flows[1].is_midstream is False
