from typing import TYPE_CHECKING

from src.packet.reader import PacketRecord

if TYPE_CHECKING:
    from src.packet.flows import Flow

# TCP Flag bitmasks
FLAG_FIN = 0x01
FLAG_SYN = 0x02
FLAG_RST = 0x04
FLAG_PSH = 0x08
FLAG_ACK = 0x10
FLAG_URG = 0x20


def packet_to_symbol(record: PacketRecord) -> str:
    """
    Map TCP flags and payload length to a formal event symbol.

    Precedence order per Doc 07 §3.3:
    1. RST set                 -> 'RST'
    2. SYN and ACK set         -> 'SYNACK'
    3. SYN set                 -> 'SYN'
    4. FIN set                 -> 'FIN'
    5. payload length > 0      -> 'DATA'
    6. ACK set (no payload)    -> 'ACK'
    7. anything else           -> 'OTHER' (causes UNKNOWN_EVENT in validator)

    Args:
        record: Extracted PacketRecord.

    Returns:
        str: Event symbol from {RST, SYNACK, SYN, FIN, DATA, ACK, OTHER}.
    """
    flags = record.tcp_flags
    has_rst = bool(flags & FLAG_RST)
    has_syn = bool(flags & FLAG_SYN)
    has_ack = bool(flags & FLAG_ACK)
    has_fin = bool(flags & FLAG_FIN)

    # 1. RST set
    if has_rst:
        return "RST"

    # 2. SYN and ACK set
    if has_syn and has_ack:
        return "SYNACK"

    # 3. SYN set
    if has_syn:
        return "SYN"

    # 4. FIN set
    if has_fin:
        return "FIN"

    # 5. Payload length > 0
    if record.payload_len > 0:
        return "DATA"

    # 6. ACK set (no payload)
    if has_ack:
        return "ACK"

    # 7. Odd or null flags
    return "OTHER"


def to_events(flow: "Flow") -> list[str]:
    """
    Map all packets in a Flow to a sequence of event symbols.

    Args:
        flow: Reconstructed TCP Flow object.

    Returns:
        list[str]: Sequence of event symbols.
    """
    return [packet_to_symbol(rec) for rec in flow.records]
