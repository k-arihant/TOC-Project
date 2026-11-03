from src.packet.mapper import (
    FLAG_ACK,
    FLAG_FIN,
    FLAG_PSH,
    FLAG_RST,
    FLAG_SYN,
    packet_to_symbol,
)
from src.packet.reader import PacketRecord


def make_record(flags: int, payload_len: int = 0) -> PacketRecord:
    return PacketRecord(
        timestamp=1000.0,
        src_ip="192.168.1.10",
        dst_ip="192.168.1.20",
        src_port=54321,
        dst_port=80,
        tcp_flags=flags,
        payload_len=payload_len,
        packet_idx=0,
    )


def test_mapper_rst_precedence():
    # RST alone
    assert packet_to_symbol(make_record(FLAG_RST)) == "RST"
    # RST + ACK + PSH
    assert packet_to_symbol(make_record(FLAG_RST | FLAG_ACK | FLAG_PSH)) == "RST"
    # RST + SYN (RST takes precedence over SYN)
    assert packet_to_symbol(make_record(FLAG_RST | FLAG_SYN)) == "RST"


def test_mapper_synack_precedence():
    # SYN + ACK
    assert packet_to_symbol(make_record(FLAG_SYN | FLAG_ACK)) == "SYNACK"
    # SYN + ACK with payload still maps to SYNACK
    assert packet_to_symbol(make_record(FLAG_SYN | FLAG_ACK, payload_len=10)) == "SYNACK"


def test_mapper_syn():
    assert packet_to_symbol(make_record(FLAG_SYN)) == "SYN"


def test_mapper_fin():
    # FIN takes precedence over DATA and ACK
    assert packet_to_symbol(make_record(FLAG_FIN | FLAG_ACK, payload_len=5)) == "FIN"
    assert packet_to_symbol(make_record(FLAG_FIN)) == "FIN"


def test_mapper_data():
    # payload > 0 with ACK
    assert packet_to_symbol(make_record(FLAG_ACK | FLAG_PSH, payload_len=128)) == "DATA"


def test_mapper_ack():
    # ACK with 0 payload
    assert packet_to_symbol(make_record(FLAG_ACK, payload_len=0)) == "ACK"


def test_mapper_other():
    # No flags set
    assert packet_to_symbol(make_record(0, payload_len=0)) == "OTHER"
