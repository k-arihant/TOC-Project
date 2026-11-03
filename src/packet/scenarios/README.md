# Packet Validation Scenarios (Tier A Lab)

This directory documents the scripted laboratory reproduction commands for Tier-A network scenarios per `07_Real_Packet_Validation.md` §2.

## Scenario Overview

| Scenario | Name | Scripted Generation | Expected Verdict |
|---|---|---|---|
| **S1** | Normal HTTP Request | `curl -s http://127.0.0.1:8000/health` | `ACCEPTED_CLEAN` (T6) |
| **S2** | Closed Port Connection | `curl -s http://127.0.0.1:9999` (closed port) | `ACCEPTED_RESET` (T7, SYN → RST) |
| **S3** | Abrupt Connection Abort | Client kills socket mid-stream | `ACCEPTED_RESET` (T7, RST) |
| **S4** | Truncated Capture | Sniffer stopped mid-transfer before FIN | `INCOMPLETE` (T1..T5) |
| **S5** | Mutated Event Sequence | Programmatically swapped/deleted packets | `INVALID` (ILLEGAL_TRANSITION) |

## Capturing via tcpdump / Wireshark

To produce a clean loopback capture for test evaluation:
```bash
# Capture loopback TCP traffic for 500 packets:
tcpdump -i lo -c 500 -w sample_loopback.pcap "tcp and port 8000"
```

## Running Evaluation CLI

Evaluate any capture using:
```bash
python -c "
from src.packet.evaluate import run_experiment
report = run_experiment('sample_loopback.pcap', profile='strict')
print(report['summary'])
"
```
