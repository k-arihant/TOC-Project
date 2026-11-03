from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from scapy.layers.inet import IP, TCP
from scapy.layers.inet6 import IPv6
from scapy.utils import PcapReader


@dataclass(frozen=True)
class PacketRecord:
    timestamp: float
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    tcp_flags: int
    payload_len: int
    packet_idx: int


def read_packets(
    path: str | Path,
    max_packets: int = 10000,
) -> Iterator[PacketRecord]:
    """
    Streaming PCAP reader using Scapy's PcapReader (avoids loading full PCAP into memory).

    Filters for IPv4 / IPv6 TCP packets only.

    Args:
        path: Path to .pcap or .pcapng file.
        max_packets: Maximum number of TCP packets to yield.

    Yields:
        PacketRecord: Extracted TCP packet metadata.
    """
    pcap_file = Path(path)
    if not pcap_file.exists():
        raise FileNotFoundError(f"PCAP file not found: {pcap_file}")

    packet_idx = 0
    with PcapReader(str(pcap_file)) as reader:
        for pkt in reader:
            if packet_idx >= max_packets:
                break

            # Must have TCP layer
            if not pkt.haslayer(TCP):
                continue

            # Extract IP layer (IPv4 or IPv6)
            if pkt.haslayer(IP):
                src_ip = str(pkt[IP].src)
                dst_ip = str(pkt[IP].dst)
            elif pkt.haslayer(IPv6):
                src_ip = str(pkt[IPv6].src)
                dst_ip = str(pkt[IPv6].dst)
            else:
                continue

            tcp_layer = pkt[TCP]
            src_port = int(tcp_layer.sport)
            dst_port = int(tcp_layer.dport)
            tcp_flags = int(tcp_layer.flags)
            payload_len = len(tcp_layer.payload)
            timestamp = float(pkt.time)

            yield PacketRecord(
                timestamp=timestamp,
                src_ip=src_ip,
                dst_ip=dst_ip,
                src_port=src_port,
                dst_port=dst_port,
                tcp_flags=tcp_flags,
                payload_len=payload_len,
                packet_idx=packet_idx,
            )
            packet_idx += 1
