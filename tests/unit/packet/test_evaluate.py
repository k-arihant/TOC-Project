from src.packet.evaluate import evaluate_flow_records
from src.packet.flows import Flow
from src.packet.mapper import FLAG_ACK, FLAG_FIN, FLAG_RST, FLAG_SYN
from src.packet.reader import PacketRecord


def make_record(flags: int, payload_len: int = 0) -> PacketRecord:
    return PacketRecord(
        timestamp=100.0,
        src_ip="127.0.0.1",
        dst_ip="127.0.0.1",
        src_port=12345,
        dst_port=8000,
        tcp_flags=flags,
        payload_len=payload_len,
        packet_idx=0,
    )


def test_evaluate_scenarios_agreement():
    # S1: Normal request -> ACCEPTED_CLEAN
    s1_flow = Flow(
        flow_id="f_s1",
        src_endpoint=("127.0.0.1", 12345),
        dst_endpoint=("127.0.0.1", 8000),
        records=[
            make_record(FLAG_SYN),
            make_record(FLAG_SYN | FLAG_ACK),
            make_record(FLAG_ACK),
            make_record(FLAG_ACK, payload_len=50),  # DATA
            make_record(FLAG_FIN),
            make_record(FLAG_FIN),
            make_record(FLAG_ACK),
        ],
        scenario="S1",
    )

    # S2: Closed port -> ACCEPTED_RESET
    s2_flow = Flow(
        flow_id="f_s2",
        src_endpoint=("127.0.0.1", 12346),
        dst_endpoint=("127.0.0.1", 9999),
        records=[
            make_record(FLAG_SYN),
            make_record(FLAG_RST),
        ],
        scenario="S2",
    )

    # S3: Abrupt abort -> ACCEPTED_RESET
    s3_flow = Flow(
        flow_id="f_s3",
        src_endpoint=("127.0.0.1", 12347),
        dst_endpoint=("127.0.0.1", 8000),
        records=[
            make_record(FLAG_SYN),
            make_record(FLAG_SYN | FLAG_ACK),
            make_record(FLAG_ACK),
            make_record(FLAG_ACK, payload_len=50),
            make_record(FLAG_RST),
        ],
        scenario="S3",
    )

    # S4: Truncated capture -> INCOMPLETE
    s4_flow = Flow(
        flow_id="f_s4",
        src_endpoint=("127.0.0.1", 12348),
        dst_endpoint=("127.0.0.1", 8000),
        records=[
            make_record(FLAG_SYN),
            make_record(FLAG_SYN | FLAG_ACK),
            make_record(FLAG_ACK),
            make_record(FLAG_ACK, payload_len=50),
        ],
        scenario="S4",
    )

    # S5: Mutated sequence -> INVALID
    s5_flow = Flow(
        flow_id="f_s5",
        src_endpoint=("127.0.0.1", 12349),
        dst_endpoint=("127.0.0.1", 8000),
        records=[
            make_record(FLAG_SYN),
            make_record(FLAG_ACK, payload_len=50),  # DATA right after SYN is ILLEGAL
        ],
        scenario="S5",
    )

    # Midstream flow -> MIDSTREAM
    midstream_flow = Flow(
        flow_id="f_mid",
        src_endpoint=("127.0.0.1", 12350),
        dst_endpoint=("127.0.0.1", 8000),
        records=[
            make_record(FLAG_ACK),
        ],
        is_midstream=True,
    )

    flows = [s1_flow, s2_flow, s3_flow, s4_flow, s5_flow, midstream_flow]
    scenario_map = {f.flow_id: f.scenario for f in flows if f.scenario}

    report = evaluate_flow_records(flows, profile="strict", scenario_map=scenario_map)

    summary = report["summary"]
    assert summary["total_flows"] == 6
    assert summary["midstream_excluded"] == 1
    assert summary["fsm_evaluated_flows"] == 5

    counts = summary["counts_by_verdict"]
    assert counts["ACCEPTED_CLEAN"] == 1
    assert counts["ACCEPTED_RESET"] == 2
    assert counts["INCOMPLETE"] == 1
    assert counts["INVALID"] == 1
    assert counts["MIDSTREAM"] == 1

    # Check scenario agreement: all 5 scenarios agreed with intended outcome
    agreement = summary["scenario_agreement"]
    assert agreement["S1"]["agreed"] == 1
    assert agreement["S2"]["agreed"] == 1
    assert agreement["S3"]["agreed"] == 1
    assert agreement["S4"]["agreed"] == 1
    assert agreement["S5"]["agreed"] == 1
